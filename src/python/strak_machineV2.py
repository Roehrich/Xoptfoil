#!/usr/bin/env python

#  This file is part of XOPTFOIL-JX.

#  XOPTFOIL-JX is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

#  XOPTFOIL-JX is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU General Public License
#  along with XOPTFOIL-JX.  If not, see <http://www.gnu.org/licenses/>.

#  Copyright (C) 2020 Matthias Boese

# imports
import xml.etree.ElementTree as ET
import argparse
import json
import sys, os
from matplotlib import pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import f90nml

# paths and separators
bs = "\\"
presetsPath = 'ressources' + bs + 'presets'
imagesPath = 'ressources' + bs + 'images'
logoName = 'strakmachine.png'

#fonts
csfont = {'fontname':'Segoe Print'}

# fontsizes
fs_infotext = 10

# colours
cl_infotext = 'aqua'

################################################################################
#
# example-dictionary for creating .json-file
#
################################################################################
strakdata = {
            # folder containing the inputs-files
            "inputFolder": 'ressources',
            # folder containing the output / result-files
            "outputFolder": 'build',
            # name of XFLR5-xml-file
            "XMLfileName": 'wing.xml',
            # Re-numbers of the strak
            "ReNumbers": [150000, 130000, 110000, 90000],
            # list of chord-lenghts
            "chordlengths": [],
            # ReSqrtCl of root airfoil
            "ReSqrtCl": '150000',
            # root airfoil name
            "seedFoilName": 'rg15.dat',
            # type of the strak that shall be developed
            "strakType":  'F3F',
             # name of the xoptfoil-inputfile for strak-airfoil(s)
            "strakInputFileName": 'i-strak.txt',
            # generate batchfile for running Xoptfoil
            "generateBatchfile" : 'true',
            # name of the batchfile
            "batchfileName" : 'make_strak.bat',
            }


################################################################################
#
# inputfile class
#
################################################################################
class inputFile:
    def __init__(self, libDir, strakType):
        self.values = {}
        self.presetInputFileName = ""
        presetInputFiles = getListOfFiles(libDir + bs + presetsPath)
        self.getInputFileName(presetInputFiles, strakType)

        # read input-file as a Fortan namelist
        self.values = f90nml.read(self.presetInputFileName)

    def getInputFileName(self, fileList, strakType):
        # search the whole list of files for the desired strak-type
        for name in fileList:
            if name.find(strakType) >= 0:
                self.presetInputFileName = name
                return

    def getPresetInputFileName(self):
        return self.presetInputFileName

    def changeTargetValue(self, keyName, targetValue):
        # get operating-conditions from dictionary
        operatingConditions = self.values["operating_conditions"]
        # get OpPoint-names
        opPointNames = operatingConditions["name"]
        idx = 0
        for key in opPointNames:
            if key == keyName:
                # change target value
                operatingConditions['target_value'][idx] = targetValue
                # write-back operatingConditions
                self.values["operating_conditions"] = operatingConditions
                return
            idx = idx + 1


    def changeOpPoint(self, keyName, op_point):
        # get operating-conditions from dictionary
        operatingConditions = self.values["operating_conditions"]
        # get OpPoint-names
        opPointNames = operatingConditions["name"]
        idx = 0
        for key in opPointNames:
            if key == keyName:
                # change op_point
                operatingConditions['op_point'][idx] = op_point
                # write-back operatingConditions
                self.values["operating_conditions"] = operatingConditions
                return
            idx = idx + 1


    def getOpPoint(self, keyName):
        # get operating-conditions from dictionary
        operatingConditions = self.values["operating_conditions"]
        # get OpPoint-names
        opPointNames = operatingConditions["name"]
        idx = 0
        for key in opPointNames:
            if key == keyName:
                # change op_point
                return operatingConditions['op_point'][idx]
            idx = idx + 1

    def adaptMaxLift(self, newClMaxLift, newAlphaMaxLift):
        self.changeOpPoint("alphaClmax", newClMaxLift)
        self.changeTargetValue("alphaClmax", newAlphaMaxLift)


    def adaptMaxGlide(self, NewMaxGlide):
        # calculate difference between old maxGlide and new maxGlide
        diff = NewMaxGlide - self.getOpPoint("maxGlide")
        newHelper = self.getOpPoint("helper") + diff
        newKeepGlide = self.getOpPoint("keepGlide") + diff

        # set new OpPoints
        self.changeOpPoint("maxGlide", NewMaxGlide)
        self.changeOpPoint("helper", newHelper)
        self.changeOpPoint("keepGlide", newKeepGlide)


    # adapt all oppoints to the give polar-data
    def adaptOppoints(self, polarData):
        ClMaxLift = polarData.CL_maxLift
        alphaMaxLift = polarData.alpha_maxLift
        self.adaptMaxLift(ClMaxLift, alphaMaxLift)

        newMaxGlide = polarData.CL_maxGlide
        self.adaptMaxGlide(newMaxGlide)

    def clearOperatingConditions(self):
         # get operating-conditions from dictionary
        operatingConditions = self.values["operating_conditions"]
        # clear operating conditions
        operatingConditions["name"] = []
        operatingConditions["op_mode"] = []
        operatingConditions["op_point"] = []
        operatingConditions["optimization_type"] = []
        operatingConditions["target_value"] = []
        operatingConditions["weighting"] = []
        operatingConditions['noppoint'] = 0


    def addOppoint(self, name, op_mode, op_point, optimization_type,
                                            target_value, weighting):
         # get operating-conditions from dictionary
        operatingConditions = self.values["operating_conditions"]
        # append new oppoint
        operatingConditions["name"].append(name)
        operatingConditions["op_mode"].append(op_mode)
        operatingConditions["op_point"].append(op_point)
        operatingConditions["optimization_type"].append(optimization_type)
        operatingConditions["target_value"].append(target_value)
        operatingConditions["weighting"].append(weighting)
        operatingConditions['noppoint'] = operatingConditions['noppoint'] + 1


    # add a "target-drag" oppoint to operating-conditions
    def addTargetPolarOppoint(self, Cl, Cd):
        self.addOppoint('target_polar', 'spec-cl', Cl, 'target-drag', Cd, 1.0)


    # delete all existing oppoints and set new ones from polar-data
    def SetOppointsFromPolar(self, polarData, numOppoints):
        Cl_min = polarData.CL[0]
        Cl_max = polarData.CL_maxLift
        Cl_increment = (Cl_max - Cl_min) / numOppoints

        # clear operating conditions
        self.clearOperatingConditions()

        # add new oppoints
        for i in range (numOppoints):
            Cl = round(Cl_min + (i * Cl_increment), 4)
            Cd = round(polarData.find_CD(Cl), 4)
            #print "Cl:%f, Cd:%f" % (Cl, Cd) #Debug
            self.addTargetPolarOppoint(Cl, Cd)


    def getMarkers(self):
        markers = []
        # get operating-conditions from dictionary
        operatingConditions = self.values["operating_conditions"]
        names = operatingConditions['name']
        for name in names:
            opPoint = self.getOpPoint(name)
            if (opPoint < 2):#TODO verbessern
                markers.append(opPoint)
        return markers


    def getOppointText(self):
        return "Dies ist ein Text"


    def writeToFile(self, fileName):
        # delete 'name'
        operatingConditions = self.values["operating_conditions"]
        operatingConditionsBackup = operatingConditions.copy()
        del(operatingConditions['name'])
        self.values["operating_conditions"] = operatingConditions

        # write to file
        print("writing input-file %s..." % fileName)
        f90nml.write(self.values, fileName, True)

        # restore 'name'
        self.values["operating_conditions"] = operatingConditionsBackup.copy()
        print("Done.")


################################################################################
#
# strakData class
#
################################################################################
class strakData:
    def __init__(self):
        self.inputFolder = ''
        self.outputFolder = ''
        self.airfoilFolder = ''
        self.xmlFileName = None
        self.strakInputFileName = 'i-strak.txt'
        self.ReSqrtCl = 150000
        self.ReNumbers = []
        self.polarFileNames = []
        self.useWingPlanform = True
        self.fromRootAirfoil= True
        self.generateBatch = True
        self.batchfileName = 'make_strak.bat'
        self.wingData = None
        self.strakType = "F3F"
        self.seedFoilName = ""
        self.polars = []


################################################################################
#
# polarData class
#
################################################################################
class polarData:
    def __init__(self):
        self.airfoilname = "airfoil"
        self.polarType = 2
        self.Re = 0
        self.NCrit = 9.0
        self.alpha = []
        self.CL = []
        self.CD = []
        self.CL_CD = []
        self.CDp = []
        self.Cm = []
        self.Top_Xtr = []
        self.Bot_Xtr= []
        self.CL_CD_max = 0
        self.maxGlide_idx = 0
        self.CL_maxGlide = 0
        self.CL_maxLift = 0
        self.alpha_maxLift = 0
        self.maxLift_idx = 0
        self.CL_Markers = []
        self.CD_Markers = []
        self.textstr = ""

    def importFromFile(self, fileName):
        BeginOfDataSectionTag = "-------"
        airfoilNameTag = "Calculated polar for:"
        ReTag = "Re ="
        parseInDataPoints = 0
        print("importing polar %s...\n" %fileName)

        # open file
        fileHandle = open(fileName)

        # parse all lines
        for line in fileHandle:

            # scan for airfoil-name
            if  line.find(airfoilNameTag) >= 0:
                splitline = line.split(airfoilNameTag)
                self.airfoilname = splitline[1]
                self.airfoilname = self.airfoilname.strip()

           # scan for Re-Number
            if  line.find(ReTag) >= 0:
                splitline = line.split(ReTag)
                splitline = splitline[1].split("Ncrit")
                Re_string = splitline[0].strip()
                splitstring = Re_string.split("e")
                faktor = float(splitstring[0].strip())
                Exponent = float(splitstring[1].strip())
                self.Re = faktor * (10**Exponent)
                self.airfoilname = self.airfoilname.strip()

            # scan for start of data-section
            if line.find(BeginOfDataSectionTag) >= 0:
                parseInDataPoints = 1
            else:
                # get all Data-points from this line
                if parseInDataPoints == 1:
                    splittedLine = line.split("  ")
                    self.alpha.append(float(splittedLine[1]))
                    self.CL.append(float(splittedLine[2]))
                    self.CD.append(float(splittedLine[3]))
                    CL_CD = float(splittedLine[2])/float(splittedLine[3])
                    self.CL_CD.append(CL_CD)
                    self.CDp.append(float(splittedLine[4]))
                    self.Cm.append(float(splittedLine[5]))
                    self.Top_Xtr.append(float(splittedLine[6]))
                    self.Bot_Xtr.append(float(splittedLine[7]))

        fileHandle.close()
        print("done.\n")


    def determineMaxGlide(self):
        # determine max-value for Cl/Cd (max glide) and corresponding Cl
        self.CL_CD_max = 0
        self.maxGlide_idx = 0
        self.CL_maxGlide = 0
        idx = 0

        for value in self.CL_CD:
            if value > self.CL_CD_max:
                self.CL_CD_max = value
                self.CL_maxGlide = self.CL[idx]
                self.maxGlide_idx = idx
            idx = idx+1
        print("max Glide, Cl/Cd = %f @ Cl = %f" %
                                  (self.CL_CD_max, self.CL_maxGlide))


    def determineMaxLift(self):
        # determine max lift-value and corresponding alpha
        self.CL_maxLift = 0
        self.alpha_maxLift = 0
        self.maxLift_idx = 0
        idx = 0

        for value in self.CL:
            if value > self.CL_maxLift:
                self.CL_maxLift = value
                self.alpha_maxLift = self.alpha[idx]
                self.maxLift_idx = idx
            idx = idx+1
        print("max Lift, Cl = %f @ alpha = %f" %
                                  (self.CL_maxLift, self.alpha_maxLift))


    def analyze(self):
        print("analysing polar...")
        self.determineMaxGlide()
        self.determineMaxLift()
        print("done.\n")


    def find_CD(self, CL):
        # calculate corresponding CD
        CD = np.interp( CL, self.CL, self.CD)
        return CD


    def SetMarkers(self, valueList):
        # add list of Cl-markers
        self.CL_Markers = valueList
        self.CD_Markers = []
        # add list of corresponding Cd-Markers
        for value in self.CL_Markers:
            self.CD_Markers.append(self.find_CD(value))

        # FIXME remove last marker, it is a lift value
        self.CL_Markers.pop()
        self.CD_Markers.pop()
        #print(self.CL_Markers) Debug
        #print(self.CD_Markers) Debug

    def SetTextstring(self, text):
        self.textstring = text


    def plotLogo(self, ax, scriptDir):
        image = mpimg.imread(scriptDir + bs + imagesPath + bs + logoName)
        ax.imshow(image)
        ax.set_axis_off()


    def plotLiftDragPolar(self, ax):
        # set axes and labels
        self.setAxesAndLabels(ax, 'Cl, Cd', 'Cd', 'Cl')

        # plot CL, CD
        ax.plot(self.CD, self.CL, 'b-')

        # set y-axis manually
        ax.set_ylim(min(self.CL) - 0.2, max(self.CL) + 0.2)

        # plot max_glide
        x = self.CD[self.maxGlide_idx]
        y = self.CL[self.maxGlide_idx]
        ax.plot(x, y, 'bo')
        ax.annotate('maxGlide @ Cl = %.2f, Cl/Cd = %.2f' % (y, (y/x)), xy=(x,y),
                      xytext=(10,0), textcoords='offset points',
                      fontsize = fs_infotext, color=cl_infotext)

        # plot max lift
        x = self.CD[self.maxLift_idx]
        y = self.CL[self.maxLift_idx]
        ax.plot(x, y, 'ro')
        ax.annotate('maxLift @ alpha = %.2f, Cl = %.2f' %(self.alpha_maxLift,
          self.CL_maxLift), xy=(x,y), xytext=(10,10), textcoords='offset points',
          fontsize = fs_infotext, color=cl_infotext)

        # plot additional markers
        ax.plot(self.CD_Markers, self.CL_Markers,'ro')


    def plotLiftAlphaPolar(self, ax):
        # set axes and labels
        self.setAxesAndLabels(ax, 'Cl, alpha', 'alpha', 'Cl')

        # plot CL, alpha
        ax.plot(self.alpha, self.CL, 'b-')

        # plot max lift
        x = self.alpha[self.maxLift_idx]
        y = self.CL[self.maxLift_idx]
        ax.plot(x, y, 'ro')

        # set y-axis manually
        ax.set_ylim(min(self.CL) - 0.1, max(self.CL) + 0.2)

        # additonal text
        ax.annotate('maxLift @ alpha = %.2f, Cl = %.2f' %(self.alpha_maxLift,
          self.CL_maxLift), xy=(x,y), xytext=(-80,15), textcoords='offset points',
          fontsize = fs_infotext, color=cl_infotext)


    def setAxesAndLabels(self, ax, title, xlabel, ylabel):

        # set title of the plot
        text = (title)
        #ax.set_title(text, fontsize = 30, color="darkgrey")

        # set axis-labels
        ax.set_xlabel(xlabel, fontsize = 20, color="darkgrey")
        ax.set_ylabel(ylabel, fontsize = 20, color="darkgrey")

        # customize grid
        ax.grid(True, color='darkgrey',  linestyle='-.', linewidth=0.7)


    def plotLiftDragAlphaPolar(self, ax):
        # set axes and labels
        self.setAxesAndLabels(ax, 'Cl/Cd, alpha', 'alpha', 'Cl/Cd')

        # plot CL/CD, alpha
        ax.plot(self.alpha, self.CL_CD, 'b-')

        # set y-axis manually
        ax.set_ylim(min(self.CL_CD) - 10, max(self.CL_CD) + 10)

        # plot max_glide
        x = self.alpha[self.maxGlide_idx]
        y = self.CL_CD[self.maxGlide_idx]
        ax.plot(x, y, 'ro')
        ax.annotate('maxGlide @ alpha = %.2f, Cl/Cd = %.2f' % (x, y), xy=(x,y),
                      xytext=(10,10), textcoords='offset points', fontsize = fs_infotext, color=cl_infotext)


    def draw(self, scriptDir):
        print("plotting polar of airfoil %s at Re = %.0f..."
                       % (self.airfoilname, self.Re))

        # set 'dark' style
        plt.style.use('dark_background')

        # setup subplots
        fig, (upper,lower) = plt.subplots(2,2)

        if (self.polarType == 2):
            text = ("Analysis of root-airfoil \"%s\" at ReSqrt(Cl) = %d, Type %d polar" %
                     (self.airfoilname, self.Re, self.polarType))
        else:
            text = ("Analysis of root-airfoil \"%s\" at Re = %d, Type %d polar" %
                     (self.airfoilname, self.Re, self.polarType))

        fig.suptitle(text, fontsize = 20, color="darkgrey", **csfont)

        # first figure, display strak-machine-logo
        self.plotLogo(upper[0], scriptDir)

        # second figure, display the Lift / Drag-Polar
        self.plotLiftDragPolar(lower[0])

        # third figure, display the Lift / alpha-Polar
        self.plotLiftAlphaPolar(upper[1])

        # fourth figure, display the lift/drag /alpha polar
        self.plotLiftDragAlphaPolar(lower[1])

        # maximize window
        figManager = plt.get_current_fig_manager()
        figManager.window.showMaximized()

        # show diagram
        plt.show()

################################################################################
# Input function that checks python version
def my_input(message):

  # Check python version

  python_version = version_info[0]

  # Issue correct input command

  if (python_version == 2):
    return raw_input(message)
  else:
    return input(message)


################################################################################
# function that gets the name of the wing
def get_wingName(wing):
    for name in wing.iter('Name'):
        return name.text

    # name was not found, return default-name
    return 'wing'


################################################################################
# function, that gets the chord-length of a section
def get_chordFromSection(section):
    # create an empty list
    chordList = []

    # iterate through elements
    for chord in section.iter('Chord'):
        # convert text to float
        chordlength = float(chord.text.strip("\r\n\t '"))

        #append chordlength to list
        chordList.append(chordlength)

    return chordList


################################################################################
# function that gets the airfoil-name of a section
def get_airfoilNameFromSection(section):
    # create an empty list
    airfoilNameList = []

    # iterate through elements
    for airfoilName in section.iter('Left_Side_FoilName'):

        #append airfoilName to list
        airfoilNameList.append(airfoilName.text)

    return airfoilNameList


################################################################################
# function that gets the chord-lengths of the wing
def get_wingChords(wing):
    # iterate the elements of the wing
    for section in wing.iter('Sections'):
        return get_chordFromSection(section)


################################################################################
# function that gets the airfoil-names of the wing
def get_airfoilNames(wing):
    # iterate the elements of the wing
    for section in wing.iter('Sections'):
        return get_airfoilNameFromSection(section)


################################################################################
# function that reads plane-data from XFLR5 XML-file
def read_planeDataFile(fileName):

    # init data as an empty list
    data = []

    # parse the file containing XFLR5-plane-data
    tree = ET.parse(fileName)

    #get root of XML-tree
    root = tree.getroot()

    # find wing-data
    for wing in root.iter('wing'):
        # create dictionary containg the wing-data
        wingDict = 	{ 'name': get_wingName(wing),
                      'chordLengths': get_wingChords(wing),
                      'airfoilNames': get_airfoilNames(wing)
                    }

        #append dictionary to data
        data.append(wingDict)

    # debug output
    #print data
    return data


################################################################################
# function that gets the name of an airfoil
def get_FoilName(params, index):

    # is there wingdata available ?
    if (params.wingData <> None):
        # yes
        wing = params.wingData
        # get airfoil-names from wing-dictionary
        airfoilNames = wing.get('airfoilNames')
        foilName = airfoilNames[index]
    else:
        # compose foilname with seedfoilname and Re-number
        Re = params.ReNumbers[index]
        # strip .dat ending
        foilName = params.seedFoilName.strip('.dat')

        if (index == 0):
            suffix = '-root'
        else:
            suffix = '-strak'

        foilName = (foilName + "%s-%03dk.dat") % (suffix,(Re/1000))

    return (foilName)

################################################################################
# function that gets the number of chords
def get_NumberOfAirfoils(params):

    # is there wingdata available ?
    if (params.wingData <> None):
        # get number of chords from wing-data
        num = len(params.wingData.get('chordLengths'))
    else:
        # get number of chords from ReNumbers
        num = len(params.ReNumbers)

    return num


################################################################################
# function that returns a list of Re-numbers
def get_ReList(params):
    list = []
    # is there wingdata available ?
    if (params.wingData <> None):
        # get list of all chord-lengths
        chordLengths = params.wingData.get('chordLengths')
        # get Re-number of root-airfoil
        rootRe = params.ReNumbers[0]
        # get chord-length of root-airfoil
        rootChord = chordLengths[0]
        # calculate list of Re-numbers
        for chord in chordLengths:
            Re = (rootRe * chord) / rootChord
            list.append(Re)
    else:
        # get list of ReNumbers from params
        list = params.ReNumbers

    return list

################################################################################
# function that generates commandlines to run Xoptfoil
def generate_commandlines(params):

    # create an empty list of commandlines
    commandLines = []

    # do some initializations / set local variables
    seedFoilName = params.seedFoilName.strip('.dat') +'.dat'
    numFoils = get_NumberOfAirfoils(params)
    ReList = get_ReList(params)

    # change current working dir to output folder
    commandline = "cd %s\n" % params.outputFolder
    commandLines.append(commandline)

    # make directory for polars of root-airfoil
    root_polar_dir = "%s_polars" % (get_FoilName(params, 0).strip('.dat'))
    commandline = ("md %s\n") % root_polar_dir
    commandLines.append(commandline)

    # copy rootfoil polars
    commandline = ("copy .."+bs+"foil_polars"+bs+"*.* %s"+bs+"*.*\n") %\
                   root_polar_dir
    commandLines.append(commandline)

    # copy seedFoil with its original name to output-folder
    commandline = ("copy .." + bs +"%s"+ bs + "%s %s\n") % \
    (params.inputFolder, seedFoilName, seedFoilName)
    commandLines.append(commandline)

    # copy master-input-file to output-folder
    inputfile = params.strakInputFileName
    commandline = ("copy .." + bs +"%s"+ bs + "%s %s\n") % \
                             (params.inputFolder, inputfile, inputfile)
    commandLines.append(commandline)

    # rename seedfoil inside outputfolder
    commandline = ("change_airfoilname.py -i .." + bs + params.inputFolder
                + bs +"%s -o %s\n") % (seedFoilName, get_FoilName(params, 0))
    commandLines.append(commandline)

    # copy (renamed) seedFoil to airfoil-folder as it can be used
    # as the root airfoil without optimization
    commandline = ("copy %s %s" + bs + "%s\n") % \
    (get_FoilName(params, 0), params.airfoilFolder, get_FoilName(params, 0))
    commandLines.append(commandline)

    # add command-lines for each strak-airfoil
    # skip the root airfoil (as it was already copied)
    for i in range (1, numFoils):
        # get name of the airfoil
        strakFoilName = get_FoilName(params, i)

        #set input-file name for Xoptfoil
        iFile = params.strakInputFileName

        # generate Xoptfoil-commandline
        commandline = "xoptfoil-jx -i %s -r %d -a %s -o %s\n" %\
                        (iFile, ReList[i], seedFoilName.strip('.dat') + '.dat',
                         strakFoilName.strip('.dat'))
        commandLines.append(commandline)

        #copy strak-airfoil to airfoil-folder
        commandline = ("copy %s %s" + bs +"%s\n") % \
            (strakFoilName , params.airfoilFolder, strakFoilName)
        commandLines.append(commandline)

    # change current working dir back
    commandline = "cd..\n"
    commandLines.append(commandline)

    return commandLines, ReList


################################################################################
# function that generates a Xoptfoil-batchfile
def generate_batchfile(batchFileName, commandlines):
    try:
        # create a new file
        outputfile = open(batchFileName, "w+")
    except:
        print ('Error, file %s could not be opened' % batchFileName)
        return

    # write Xoptfoil-commandline to outputfile
    for element in commandlines:
        outputfile.write(element)

    # close the outputfile
    outputfile.close()


################################################################################
# function that gets the name of the strak-machine-data-file
def getInFileName(args):

    if args.input:
        inFileName = args.input
    else:
        # use Default-name
        inFileName = 'ressources/strakdata'

    inFileName = inFileName + '.txt'
    print("filename for strak-machine input-data is: %s" % inFileName)
    return inFileName


################################################################################
# function that gets arguments from the commandline
def getArguments():

    # initiate the parser
    parser = argparse.ArgumentParser('')

    parser.add_argument("-input", "-i", help="filename of strak-machine input"\
                        "-file (e.g. strak_data)")

    # read arguments from the command line
    args = parser.parse_args()
    return (getInFileName(args))


################################################################################
# function that gets parameters from dictionary
def getParameters(dict):

    params = strakData()

    try:
        params.inputFolder = dict["inputFolder"]
    except:
        print ('inputFolder not specified, assuming no input-folder shall be used.')

    try:
        params.outputFolder = dict["outputFolder"]
    except:
        print ('outputFolder not specified, assuming no output-folder shall be used.')

    try:
        params.batchfileName = dict["batchfileName"]
    except:
        print ('batchfileName not found, setting default-filename \'%s\'.'\
                % params.batchfileName)

    try:
        params.xmlFileName = dict["XMLfileName"]
    except:
        print ('XMLfileName not specified, assuming no xml-file shall be used.')

    try:
        params.strakInputFileName = dict["strakInputFileName"]
    except:
        print ('strakInputFileName not found, setting default-filename \'%s\'.'\
                % params.strakInputFileName)

    try:
        params.ReNumbers = dict["ReNumbers"]
    except:
        print ('ReNumbers not specified, using no list of ReNumbers')

    try:
        params.seedFoilName = dict["seedFoilName"].strip('.dat')
    except:
        print ('seedFoilName not specified')

    try:
        params.strakType = dict["strakType"]
    except:
        print ('strakType not specified')

    return params


def getListOfFiles(dirName):
    # create a list of files in the given directory
    listOfFile = os.listdir(dirName)
    allFiles = list()

    # Iterate over all the entries
    for entry in listOfFile:
        # Create full path
        fullPath = os.path.join(dirName, entry)
        allFiles.append(fullPath)

    return allFiles


def getwingDataFromXML(params):

    xmlFileName = params.inputFolder + '/' + params.xmlFileName
    try:
        planeData = read_planeDataFile(xmlFileName)
    except:
        print("Error, file \"%s\" could not be opened.") % xmlFileName
        exit(-1)

    # return data
    print planeData[0]
    return planeData[0]

def getwingDataFromParams(params):
    return
################################################################################
# Main program
if __name__ == "__main__":

    # get command-line-arguments or user-input
    strakDataFileName = getArguments()

    # get real path of the script
    pathname = os.path.dirname(sys.argv[0])
    scriptPath = os.path.abspath(pathname)

##    #debug
##    out_file = open("strakdata.txt",'w')
##    json.dump(strakdata, out_file, indent = 6)
##    out_file.close()

    # try to open .json-file
    try:
        strakDataFile = open(strakDataFileName)
    except:
        print('Error, failed to open file %s' % strakDataFileName)
        exit(-1)

    # load dictionary from .json-file
    try:
        strakdata = json.load(strakDataFile)
        strakDataFile.close()
    except:
        print('Error, failed to read data from file %s' % strakDataFileName)
        strakDataFile.close()
        exit(-1)

    # get strak-machine-parameters from dictionary
    params = getParameters(strakdata)
    # print strakdata

    # read plane-data from XML-File, if requested //TODO: only wing-data
    if (params.xmlFileName != None):
        params.wingData = getwingDataFromXML(params)

    # compose name of the folder, where the airfoils shall be stored
    params.airfoilFolder = 'airfoils'

    # get current working dir
    workingDir = os.getcwd()

    # check if output-folder exists. If not, create folder.
    if not os.path.exists(params.outputFolder):
        os.makedirs(params.outputFolder)

    # check if airfoil-folder exists. If not, create folder.
    if not os.path.exists(params.outputFolder + '\\' + params.airfoilFolder):
        os.makedirs(params.outputFolder + '\\' + params.airfoilFolder)

    # generate Xoptfoil command-lines
    commandlines, ReList = generate_commandlines(params)

    # debug-output
    for element in commandlines:
        print element

    # generate batchfile
    if (params.generateBatch == True):
        print ('generating batchfile \'%s\'' % params.batchfileName)
        generate_batchfile(params.batchfileName, commandlines)

    # create instance of new inputfile, automatically get preset-values for
    # strak-Type
    newInputFile = inputFile(scriptPath, params.strakType)

    # generate polars of seedfoil / root-airfoil:
    # get name of root-airfoil
    seedFoilName = params.seedFoilName.strip('.dat')+ '.dat'

    print("Generating polars for airfoil %s" % seedFoilName)

    polarDir = workingDir + bs + "foil_polars"

    # create list of polar-file-Names from Re-Numbers
    for Re in params.ReNumbers:
        # create list of polar-file-Names from Re-Numbers
        polarFileName = "T2_Re0.%03d_M0.00_N9.0.txt" % (Re/1000)
        polarFileName = polarDir + bs + polarFileName
        params.polarFileNames.append(polarFileName)

        # compose string for system-call of XFOIL-worker
        airfoilName = workingDir + bs + params.inputFolder + bs + seedFoilName
        systemString = "xfoil_worker.exe -i %s -w polar -a %s -r %d" % (
           newInputFile.getPresetInputFileName(), airfoilName, Re)
        print systemString #Debug

        # execute xfoil-worker
        os.system(systemString)

        # import polar
        newPolar = polarData()
        newPolar.importFromFile(polarFileName)
        newPolar.analyze()
        params.polars.append(newPolar)

    print("Done.")

    rootPolar = params.polars[0]

    # adapt oppoints of inputfile according to generated polar of root airfoil
    newInputFile.adaptOppoints(rootPolar)

    # write new input-file with the given filename
    newInputFile.writeToFile(params.inputFolder + bs + params.strakInputFileName)

    # Get some Markers to show in the polar-plot from the input-file
    rootPolar.SetMarkers(newInputFile.getMarkers())

    # Get text-description that will be shown in a textbox
    rootPolar.SetTextstring(newInputFile.getOppointText())

    # TODO SetOppointsFromPolar
    for i in range(1, len(params.ReNumbers)):
        filename = params.inputFolder + bs + params.strakInputFileName
        filename = filename.strip('.txt')
        filename = filename + ("_%03dk.txt" % (params.ReNumbers[i]/1000))
        newFile = inputFile(scriptPath, params.strakType)
        # TODO change polar
        newFile.SetOppointsFromPolar(params.polars[i], 10)
        newFile.writeToFile(filename)

    # show diagram
    rootPolar.draw(scriptPath)

    print("Ready.")
