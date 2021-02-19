!  This file is part of XOPTFOIL.

!  XOPTFOIL is free software: you can redistribute it and/or modify
!  it under the terms of the GNU General Public License as published by
!  the Free Software Foundation, either version 3 of the License, or
!  (at your option) any later version.

!  XOPTFOIL is distributed in the hope that it will be useful,
!  but WITHOUT ANY WARRANTY; without even the implied warranty of
!  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
!  GNU General Public License for more details.

!  You should have received a copy of the GNU General Public License
!  along with XOPTFOIL.  If not, see <http://www.gnu.org/licenses/>.

!  Copyright (C) 2017-2019 Daniel Prosser

module optimization_driver

! Contains subroutines to set options and conditions for optimization and to
! issue optimizer calls

  implicit none

  contains

!=============================================================================80
!
! Preprocessing for non-aerodynamic optimization
!
!=============================================================================80
subroutine matchfoils_preprocessing(matchfoil_file)

  use vardef,             only : airfoil_type, foil_to_match, symmetrical, npan_fixed
  use vardef,             only : seed_foil
  use airfoil_operations, only : get_seed_airfoil,  rebuild_airfoil, my_stop
  use airfoil_operations, only : repanel_and_normalize_airfoil
  use math_deps,          only : interp_vector
  use naca,               only : naca_options_type
  use os_util,            only : print_note

  
  character(*), intent(in) :: matchfoil_file

  type(airfoil_type) :: original_foil
  type(naca_options_type) :: dummy_naca_options
  integer :: pointst, pointsb
  double precision, dimension(:), allocatable :: zttmp, zbtmp, xmatcht, xmatchb, zmatcht, zmatchb

  call print_note ('Using the optimizer to match the seed airfoil to the '//&
                   'airfoil about to be loaded.')

! Check if symmetrical airfoil was requested (not allowed for this type)

  if (symmetrical)                                                             &
    call my_stop("Symmetrical airfoil constraint not permitted for non-"//&
                 "aerodynamic optimizations.")

! Load airfoil to match

  call get_seed_airfoil('from_file', matchfoil_file, dummy_naca_options, original_foil)

! Repanel to npan_fixed points and normalize to get LE at 0,0 and TE (1,0) and split

  call repanel_and_normalize_airfoil (original_foil, npan_fixed, foil_to_match)

  xmatcht = foil_to_match%xt
  xmatchb = foil_to_match%xb
  zmatcht = foil_to_match%zt
  zmatchb = foil_to_match%zb

! Interpolate x-vals of foil to match to seed airfoil points to x-vals 
!    - so the z-values can later be compared

  pointst = size(seed_foil%xt,1)
  pointsb = size(seed_foil%xb,1)
  allocate(zttmp(pointst))
  allocate(zbtmp(pointsb))
  zttmp(pointst) = zmatcht(size(zmatcht,1))
  zbtmp(pointsb) = zmatchb(size(zmatchb,1))
  call interp_vector(xmatcht, zmatcht, seed_foil%xt(1:pointst-1),                    &
                     zttmp(1:pointst-1))
  call interp_vector(xmatchb, zmatchb, seed_foil%xb(1:pointsb-1),                    &
                     zbtmp(1:pointsb-1))

! Re-set coordinates of foil to match from interpolated points
    
  call rebuild_airfoil(seed_foil%xt, seed_foil%xb, zttmp, zbtmp, foil_to_match)

end subroutine matchfoils_preprocessing



!=============================================================================80
!
! Subroutine to drive the optimization
!
!=============================================================================80
subroutine optimize(search_type, global_search, local_search, constrained_dvs, &
                    pso_options, ga_options, ds_options, restart,              &
                    restart_write_freq, optdesign, f0_ref, fmin, steps, fevals)

  use vardef,             only : shape_functions, nflap_optimize,              &
                                 initial_perturb, min_flap_degrees,            &
                                 max_flap_degrees, flap_degrees,               &
                                 flap_optimize_points, min_bump_width,         &
                                 output_prefix 
  use particle_swarm,     only : pso_options_type, particleswarm
  use genetic_algorithm,  only : ga_options_type, geneticalgorithm
  use simplex_search,     only : ds_options_type, simplexsearch
  use airfoil_evaluation, only : objective_function,                           &
                                 objective_function_nopenalty, write_function

  character(*), intent(in) :: search_type, global_search, local_search
  type(pso_options_type), intent(in) :: pso_options
  type(ga_options_type), intent(in) :: ga_options
  type(ds_options_type), intent(in) :: ds_options
  double precision, dimension(:), intent(inout) :: optdesign
  double precision, intent(out) :: f0_ref, fmin
  integer, intent(in) :: restart_write_freq
  integer, dimension(:), intent(in) :: constrained_dvs
  integer, intent(out) :: steps, fevals
  logical, intent(in) :: restart

  integer :: counter, nfuncs, ndv
  double precision, dimension(size(optdesign,1)) :: xmin, xmax, x0
  double precision :: t1fact, t2fact, ffact
  logical :: restart_temp, write_designs
  integer :: stepsg, fevalsg, stepsl, fevalsl, i, oppoint, stat,               &
             iunit, ioerr, designcounter
  character(100) :: restart_status_file
  character(19) :: restart_status
  character(14) :: stop_reason

! Delete existing run_control file and rewrite it

  iunit = 23
  open(unit=iunit, file='run_control', status='replace')
  close(iunit)

! Delete existing optimization history for visualizer to start new
  
  if (.not. restart) then 
    iunit = 17
    open(unit=iunit, file='optimization_history.dat', status='replace')
    close(iunit)
  end if 
    
! Restart status file setup

  iunit = 15
  restart_status_file = 'restart_status_'//trim(output_prefix)

! Perform optimization: global, local, or global + local

  stepsg = 0
  fevalsg = 0
  stepsl = 0
  fevalsl = 0
  designcounter = 0

  ndv = size(optdesign,1)

! Scale all variables to have a range of initial_perturb
  t1fact = initial_perturb/(1.d0 - 0.001d0)
  t2fact = initial_perturb/(10.d0 - min_bump_width)
  ffact = initial_perturb/(max_flap_degrees - min_flap_degrees)

! Set initial design

  if ((trim(shape_functions) == 'naca') .or. &
      (trim(shape_functions) == 'camb-thick') .or. &
      (trim(shape_functions) == 'camb-thick-plus')) then     
  !----------naca / camb-thick ----------

    nfuncs = ndv - nflap_optimize

!   Mode strength = 0 (aka seed airfoil)

    x0(1:nfuncs) = 0.d0

!   Seed flap deflection as specified in input file

    do i = nfuncs + 1, ndv
      oppoint = flap_optimize_points(i-nfuncs)
      x0(i) = flap_degrees(oppoint)*ffact
    end do
  else
  !------------hicks-henne-------------
    
    nfuncs = (ndv - nflap_optimize)/3

!   Bump strength = 0 (aka seed airfoil)
    do i = 1, nfuncs
      counter = 3*(i-1)
      x0(counter+1) = 0.d0
      x0(counter+2) = 0.5d0*t1fact
      x0(counter+3) = 1.d0*t2fact
    end do
    do i = 3*nfuncs+1, ndv
      oppoint = flap_optimize_points(i-3*nfuncs)
      x0(i) = flap_degrees(oppoint)*ffact
    end do

  end if

! Compute f0_ref, ignoring penalties for violated constraints

  f0_ref = objective_function_nopenalty(x0) 

  
! Set default restart status (global or local optimization) from user input

  if (trim(search_type) == 'global_and_local' .or. trim(search_type) ==    &
      'global') then
    restart_status = 'global_optimization'
  else
    restart_status = 'local_optimization'
  end if


! Design coordinates/polars output handling

  write_designs = .false.
  if ( (trim(search_type) == 'global_and_local') .or.                          &
       (trim(search_type) == 'global') ) then
    if ( (pso_options%write_designs) .or. (ga_options%write_designs) )         &
      write_designs = .true.
  else
    if (ds_options%write_designs) write_designs = .true.
  end if
    
! Write seed airfoil coordinates and polars to file

  if (write_designs) then

!   Analyze and write seed airfoil
    stat = write_function(x0, 0) 

  end if

! Set temporary restart variable

  restart_temp = restart

! Global optimization

  if (trim(restart_status) == 'global_optimization') then

!   Set up mins and maxes
    
    if ((trim(shape_functions) == 'naca') .or. &
        (trim(shape_functions) == 'camb-thick') .or. &
        (trim(shape_functions) == 'camb-thick-plus')) then

      nfuncs = ndv - nflap_optimize

      xmin(1:nfuncs) = -0.5d0*initial_perturb
      xmax(1:nfuncs) = 0.5d0*initial_perturb
      xmin(nfuncs+1:ndv) = min_flap_degrees*ffact
      xmax(nfuncs+1:ndv) = max_flap_degrees*ffact

    else

      nfuncs = (ndv - nflap_optimize)/3

      do i = 1, nfuncs
        counter = 3*(i-1)
        xmin(counter+1) = -initial_perturb/2.d0
        xmax(counter+1) = initial_perturb/2.d0
        xmin(counter+2) = 0.0001d0*t1fact
        xmax(counter+2) = 1.d0*t1fact
        xmin(counter+3) = min_bump_width*t2fact
        xmax(counter+3) = 10.d0*t2fact
      end do
      do i = 3*nfuncs+1, ndv
        xmin(i) = min_flap_degrees*ffact
        xmax(i) = max_flap_degrees*ffact
      end do

    end if

    if (trim(global_search) == 'particle_swarm') then

!     Particle swarm optimization
      call particleswarm(optdesign, fmin, stepsg, fevalsg, objective_function, &
                         x0, xmin, xmax, .true., f0_ref, constrained_dvs,      &
                         pso_options, designcounter, stop_reason, write_function)

    else if (trim(global_search) == 'genetic_algorithm') then

!     Genetic algorithm optimization

      call geneticalgorithm(optdesign, fmin, stepsg, fevalsg,                  &
                            objective_function, x0, xmin, xmax, .true.,        &
                            f0_ref, constrained_dvs, ga_options, restart_temp, &
                            restart_write_freq, designcounter, stop_reason,    &
                            write_function)

    end if

!   Update restart status and turn off restarting for local search

    if ( (stop_reason == "completed") .and.                                    &
         (trim(search_type) == 'global_and_local') )                           &
        restart_status = 'local_optimization'
    restart_temp = .false.

  end if

! Local optimization

  if (restart_status == 'local_optimization') then

    if (trim(local_search) == 'simplex') then

!     Simplex optimization

      if (trim(search_type) == 'global_and_local') then
        x0 = optdesign  ! Copy x0 from global search result
      end if

      call simplexsearch(optdesign, fmin, stepsl, fevalsl, objective_function, &
                         x0, .true., f0_ref, ds_options, restart_temp,         &
                         restart_write_freq, designcounter, stepsg,            &
                         write_function)

    end if

  end if

! Total number of steps and function evaluations

  steps = stepsg + stepsl
  fevals = fevalsg + fevalsl

! Write stop_monitoring command to run_control file

  iunit = 23
  open(unit=iunit, file='run_control', status='old', position='append',        &
       iostat=ioerr)
  if (ioerr /= 0) open(unit=iunit, file='run_control', status='new')
  write(iunit,'(A)') "stop_monitoring"
  close(iunit)

end subroutine optimize

!=============================================================================80
!
! Writes final airfoil design to a file
!    Returns final airfoil 
!
!=============================================================================80
subroutine write_final_design(optdesign, f0, fmin, final_airfoil)

  use vardef
  use airfoil_operations, only : airfoil_write
  use xfoil_driver,       only : run_xfoil
  use airfoil_evaluation, only : create_airfoil_form_design, get_flap_degrees_from_design
  use airfoil_evaluation, only : xfoil_geom_options, xfoil_options

  double precision, dimension(:), intent(in) :: optdesign
  double precision, intent(in)               :: f0, fmin
  type(airfoil_type), intent(out)            :: final_airfoil

  double precision, dimension(noppoint) :: alpha, lift, drag, moment, cpmin, &
                                           xacct, xaccb, xtrt, xtrb
  logical,          dimension(noppoint) :: op_converged, sept, sepb
  double precision, dimension(noppoint) :: actual_flap_degrees
  integer :: i, iunit
  character(80) :: output_file, aero_file
  character(20) :: flapnote

  
! Rebuild foil out final design and seed airfoil

  call create_airfoil_form_design (seed_foil, optdesign, final_airfoil)
  
  final_airfoil%name   = output_prefix

! Use Xfoil to analyze final design

  if (.not. match_foils) then

!   Get actual flap angles based on design variables

    call get_flap_degrees_from_design (optdesign, actual_flap_degrees)

!   Run xfoil for requested operating points

    call run_xfoil(final_airfoil, xfoil_geom_options, op_point(1:noppoint),    &
                   op_mode(1:noppoint), re(1:noppoint), ma(1:noppoint),        &
                   use_flap, x_flap, y_flap, y_flap_spec,                      &
                   actual_flap_degrees(1:noppoint), xfoil_options,             &
                   op_converged, lift, drag, moment, cpmin, xacct, xaccb, &
                   sept, sepb, xsepta, xseptb, xsepba, xsepbb, alpha, xtrt, xtrb, &
                   ncrit_pt, xtript_pt, xtripb_pt)

!   Write summary to screen and file

    aero_file = trim(output_prefix)//'_performance_summary.dat'
    iunit = 13
    open(unit=iunit, file=aero_file, status='replace')

    write(*,*)
    write(*    ,'(A)') " Optimal airfoil performance summary"
    write(iunit,'(A)') " Optimal airfoil performance summary"
    write(*    ,'(A)') ""
    write(iunit,'(A)') ""

! i  alpha   CL        CD           Cm       Top Xtr Bot Xtr  Re       Mach   ncrit   flap   cpmin   xacct  xaccb  sept  sepb    E
! -- ----- ------ ------------- ------------- ------ ------ -------- ------- ------  ----- -------- ------ ------ ----- ----- -------
! 1   8.31 1.0000  2.771682E-02 -2.686485E-02 0.0547 1.0000 1.00E+05   0.000    7.0      -   0.0000 0.0003 0.6023     T     T  36.08 

    write (iunit,'(A)') " i  alpha    CL        CD           Cm       Top Xtr Bot Xtr  Re       &
          &Mach   ncrit   flap   cpmin   xacct  xaccb  sept  sepb    E"
    write (iunit,'(A)') " -- ----- ------- ------------- ------------- ------ ------ -----&
          &--- ------- ------  ----- -------- ------ ------ ----- ----- -------"
    write (*    ,'(A)') " i  alpha    CL        CD           Cm       Top Xtr Bot Xtr  Re       &
          &Mach   ncrit   flap   cpmin   xacct  xaccb  sept  sepb    E"
    write (*    ,'(A)') " -- ----- ------- ------------- ------------- ------ ------ -----&
          &--- ------- ------  ----- -------- ------ ------ ----- ----- -------"

    do i = 1, noppoint

      if (use_flap) then
        write (flapnote, '(F6.2)') actual_flap_degrees(i)
        if (flap_selection(i) == "specify") then
          flapnote = trim(flapnote) //" spec"
        else
          flapnote = trim(flapnote) //" opt"
        end if 
      else
        flapnote = "   -"
      end if   

      write (iunit,  "(I2, F7.2, F8.4, 2ES14.6, 2F7.4, ES9.2, F8.3, F7.1, 3X, A,  F9.4, 2F7.4, 2L6, F7.2)") &
        i, alpha(i), lift(i), drag(i), moment(i), xtrt(i), xtrb (i), re(i)%number, ma(i)%number, ncrit_pt(i), &
        trim(flapnote), cpmin(i), xacct(i), xaccb(i), sept(i), sepb(i), lift(i)/drag(i)
      write (*    ,  "(I2, F7.2, F8.4, 2ES14.6, 2F7.4, ES9.2, F8.3, F7.1, 3X, A,  F9.4, 2F7.4, 2L6, F7.2)") &
        i, alpha(i), lift(i), drag(i), moment(i), xtrt(i), xtrb (i), re(i)%number, ma(i)%number, ncrit_pt(i), &
        trim(flapnote), cpmin(i), xacct(i), xaccb(i), sept(i), sepb(i), lift(i)/drag(i)

    end do

    write(*,*)
    write(*,'(A43F8.4A1)') " Objective function improvement over seed: ",      &
                           (f0 - fmin)/f0*100.d0, "%" 
    write(iunit,*)
    write(iunit,'(A43F8.4A1)') " Objective function improvement over seed: ",  &
                           (f0 - fmin)/f0*100.d0, "%" 

    close(iunit)

    write(*,*)
    write(*,*) "Optimal airfoil performance summary written to "               &
               //trim(aero_file)//"."


  else
    call write_matchfoil_summary (final_airfoil%zt, final_airfoil%zb)
  end if

! Write airfoil to file

  output_file = trim(output_prefix)//'.dat'
  call airfoil_write(output_file, output_prefix, final_airfoil)

end subroutine write_final_design


!-----------------------------------------------------------------------------
! Write some data of the final match foil 
!-----------------------------------------------------------------------------
subroutine write_matchfoil_summary (zt_new, zb_new)

  use vardef, only    : seed_foil, foil_to_match
  
  double precision, dimension(size(seed_foil%xt,1)), intent(in) :: zt_new
  double precision, dimension(size(seed_foil%xb,1)), intent(in) :: zb_new
  double precision :: maxdeltat, maxdeltab, averaget, averageb, maxdt_rel, maxdb_rel

  maxdeltat = maxval(abs (zt_new - foil_to_match%zt))
  maxdeltab = maxval(abs (zb_new - foil_to_match%zb))

  maxdt_rel = (maxdeltat / maxval(abs (foil_to_match%zt))) * 100.d0
  maxdb_rel = (maxdeltab / maxval(abs (foil_to_match%zb))) * 100.d0
 
  averaget  = sum (zt_new - foil_to_match%zt) / size(seed_foil%xt,1)
  averageb  = sum (zb_new - foil_to_match%zb) / size(seed_foil%xb,1)

  write(*,*)
  write(*,'(A)') " Match airfoil deviation summary"
  write(*,*)
  write(*,'(A)') "      Delta of y-coordinate between adjusted match and seed surface"
  write(*,*)
  write(*,'(A)') "                average    max delta   to max y"

  write (*,'(A10)', advance = 'no') "   top:"
  write (*,'(1x, ES12.1, ES12.1, F10.3,A1)') averaget, maxdeltat, maxdt_rel,'%'
  write (*,'(A10)', advance = 'no') "   bot:"
  write (*,'(1x, ES12.1, ES12.1, F10.3,A1)') averageb, maxdeltab, maxdb_rel,'%'

end subroutine write_matchfoil_summary

end module optimization_driver
