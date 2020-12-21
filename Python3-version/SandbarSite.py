import re
import os
import gdal
import numpy as np
from Raster import Raster
from CSVLib import unionCSVExtents
from logger import Logger

from ClipRaster import ClipRaster

import SandbarSurvey
from SandbarSurveySection import SandbarSurveySection
from datetime import datetime

from math import ceil, isnan

class SandbarSite:

    def __init__(self, siteCode, siteCode5, siteID, dischargeA, dischargeB, dischargeC, dirSurveyFolder):
        self.siteCode = siteCode
        self.siteCode5 = siteCode5
        self.siteID = siteID
        self.disCoefficientA = dischargeA
        self.disCoefficientB = dischargeB
        self.disCoefficientC = dischargeC
        self.surveyDates = {}
        self.log = Logger("Sandbar Site")
        self.inputsSurveyFolder = dirSurveyFolder
        self.MinimumSurfacePath = "" # populated by GenerateDEMRasters()
        self.MinimumSurface = None
        self.Ignore = False # This is set to true if issues occur with the site and it can't be processed.

        assert len(self.siteCode5), "The siteCode5 field '{0}' is not five character in length.".format(siteCode5)

    def getStage(self, discharge):

        if discharge is None:
            return None
        else:
            stage = self.disCoefficientA + (self.disCoefficientB * discharge) + (self.disCoefficientC * (discharge ** 2))
            return round(stage, 2)


    def getMinAnalysisStage(self, minSurveyElevation, benchmarkDischrage, analysisIncrement):
        """
        Get the minimum analysis elevation for the calculation of sand volumes by
        increments. This is the closest value below the minimum survey elevation that is an
        even number of analysis increments (default is 0.1m) below the benchmark discharge
        (default 8000cfs)
        :param minSurveyElevation:
        :param benchmarkDischrage:
        :param analysisIncrement:
        :return:
        """
        benchmarkStage = self.getStage(benchmarkDischrage)
        minAnalysisStage = benchmarkStage - ceil((benchmarkStage - minSurveyElevation) / analysisIncrement) * analysisIncrement
        if isnan(minAnalysisStage):
            minAnalysisStage = None
        return minAnalysisStage


    def getNumericSiteCode(self):
        """
        Remove the leading zero padding and just return the numeric part of the
        site code (e.g.  0033L returns 33)
        :return:
        """
        theMatch = re.search("[0]*([0-9]+)", self.siteCode)
        if theMatch:
            return theMatch.group(1)
        else:
            return None

    def GenerateDEMRasters(self, dirSurveyFolder, fCSVCellSize, fCellSize, resampleMethod, nEPSG, bReUseRasters):
        """
        :param dirSurveyFolder:
        :param fCSVCellSize:
        :param fCellSize:
        :param resampleMethod:
        :param theExtent:
        :param nEPSG:
        :param bReUseRasters:
        :return:
        """
        demFolder = os.path.join(dirSurveyFolder, "DEMs_Unclipped")
        if not os.path.exists(demFolder):
            os.makedirs(demFolder)

        # Make sure we're clean and typed
        fCSVCellSize = float(fCSVCellSize)
        fCellSize = float(fCellSize)

        # Retrieve the union of all TXT files for this site
        csvFiles = [aDate.txtPointsPath for idx, aDate in self.surveyDates.items()]
        theExtent = unionCSVExtents(csvFiles, cellSize=fCSVCellSize, padding=10.0)
        self.log.info("Site {0}: Unioned extent for {1} surveys is {2}".format(self.siteCode5, len(self.surveyDates),
                                                                               theExtent))

        # Create a temporary template raster object we can resample
        tempRaster = Raster(proj=nEPSG, extent=theExtent, cellWidth=fCSVCellSize)
        self.log.info("Site {0}: Generating {1} rasters with {2} cols, {3} rows at {4}m cell size...".format(self.siteCode5, len(self.surveyDates), tempRaster.cols, tempRaster.rows, fCellSize))


        # Initialize the Minimum Surface Raster and give it an array of appropriate size
        self.MinimumSurfacePath = os.path.join(dirSurveyFolder, "{0}_min_surface.tif".format(self.siteCode5))
        self.MinimumSurface = Raster(proj=nEPSG, extent=theExtent, cellWidth=fCellSize)
        self.MinimumSurface.setArray(np.nan * np.empty( (self.MinimumSurface.rows, self.MinimumSurface.cols) ))


        for SurveyID, aDate in self.surveyDates.items():

            aDate.DEMPath = os.path.join(demFolder, "{0}_{1:%Y%m%d}_dem.tif".format(self.siteCode5, aDate.SurveyDate))

            # option to skip that speeds up debugging
            if os.path.isfile(aDate.DEMPath) and bReUseRasters:
               continue

            # Create a raster object that will represent the raw CSV
            rDEM = Raster(proj=nEPSG, extent=theExtent, cellWidth=fCSVCellSize)
            # This function will add the array in-place to the raster object
            rDEM.loadDEMFromCSV(aDate.txtPointsPath, theExtent)

            if fCSVCellSize != fCellSize:
                # This method resamples the array and returns a new raster object
                newDEM = rDEM.ResampleDEM(fCellSize, resampleMethod)

                # Only incorporate the DEM into the analysis if required
                if aDate.IsMinSurface:
                    self.MinimumSurface.MergeMinSurface(newDEM)

                newDEM.write(aDate.DEMPath)
            else:
                # No resample necessary.

                # Only incorporate the DEM into the analysis if required
                if aDate.IsMinSurface:
                    self.MinimumSurface.MergeMinSurface(rDEM)

                # Write the raw DEM object
                rDEM.write(aDate.DEMPath)

            assert os.path.isfile(aDate.DEMPath), "Failed to generate raster for site {0} at {1}".format(self.siteCode5, aDate.DEMPath)

        ## write the minimum surface raster to file
        if not bReUseRasters:
            assert self.MinimumSurface is not None, "Error generating minimum surface raster for site {0}".format(self.siteCode5)
            self.MinimumSurface.write(self.MinimumSurfacePath)

        assert os.path.isfile(self.MinimumSurfacePath), "Minimum surface raster is missing for site {0} at {1}".format(self.siteCode5, self.MinimumSurfacePath)

    def ClipDEMRastersToSections(self, gdal_warp, dirSurveyFolder, dSections, theCompExtent, bResUseRasters):
        """
        :param gdal_warp:
        :param dirSurveyFolder:
        :param dSections:
        :param theCompExtent:
        :param bResUseRasters:
        :return:
        """
        nClipped = 0
        nSections = 0

        for SurveyID, aDate in self.surveyDates.items():
            for nSectionTypeID, aSurveyedSection in aDate.surveyedSections.items():

                # Only attempt to produce clipped raster if the computational extent exists
                if aSurveyedSection.Ignore:
                    continue

                nSections += 1
                sectionFolder = aSurveyedSection.SectionType
                nHyphon = aSurveyedSection.SectionType.find("-")
                if nHyphon >= 0:
                    sectionFolder = aSurveyedSection.SectionType.replace(" ","").replace("-","_")

                demFolder = os.path.join(dirSurveyFolder, "DEMs_Clipped", sectionFolder)
                if not os.path.exists(demFolder):
                    os.makedirs(demFolder)

                clippedPath = os.path.join(demFolder, "{0}_{1:%Y%m%d}_{2}_dem.tif".format(self.siteCode5, aDate.SurveyDate, sectionFolder))

                # option to skip that speeds up debugging
                if not (os.path.isfile(clippedPath) and bResUseRasters):

                    # This clause ensures that only the desired features are
                    # used for the clipping
                    sWhere = theCompExtent.getFilterClause(self.siteCode5, aSurveyedSection.SectionType)
                    ClipRaster(gdal_warp, aDate.DEMPath, clippedPath, theCompExtent, sWhere)

                # Store the clipped raster in a dictionary on the survey date
                # objects
                aSurveyedSection.rasterPath = clippedPath
                nClipped += 1

        self.log.info("Site {0}: Clipped {1} rasters across {2} surveys and {3} sections defined".format(self.siteCode5, nClipped, len(self.surveyDates), nSections))

    def getElevationRange(self, dSections):
        """
        :param dSections:
        :return:
        """
        minElevation = -1.0
        maxElevation = 0.0
        for SurveyID, aDate in self.surveyDates.items():
            for nSectionTypeID, aSurveyedSection in aDate.surveyedSections.items():

                dsRaster = gdal.Open(aSurveyedSection.rasterPath)
                rbRaster = dsRaster.GetRasterBand(1)
                rasStats = rbRaster.GetStatistics(0,1)

                # The clipped DEMs might not have any data in the section
                # (channel or eddy)
                # in which case the stats returns all zeroes

                if rasStats[0] and rasStats[0] > 0:
                    if minElevation < 0:
                        minElevation = rasStats[0]
                    else:
                        minElevation = min(minElevation, rasStats[0])

                if rasStats[1] and rasStats[1] > 0:
                    maxElevation = max(maxElevation, rasStats[1])

                rb = None
                dsRaster = None

        assert minElevation > 500, "The minimum elevation ({0}) is too low.".format(minElevation)
        assert maxElevation >= minElevation, "The maximum elevation ({0}) is below the minimum elevation ({1}).".format(maxElevation,minElevation)
        self.log.info("Site {0} elevation range (across {1} surveys) is {2}".format(self.siteCode5, len(self.surveyDates), (minElevation, maxElevation)))
        return (minElevation, maxElevation)

    def verifyTXTFileFormat(self):

        for SurveyID, aDate in self.surveyDates.items():
            # Opeen the text file and verify that it has the correct number of space-separated floating point values
            with open(aDate.txtPointsPath, 'r') as f:
                theMatch = re.match("^([0-9.]+\s){3}([0-9.]+)\s*$", f.readline())
                if not theMatch:
                    self.log.warning(
                        "Site {0}: The {1} survey has an invalid text file format. Skipping loading surveys. This site will not be processed. {2}".format(
                            self.siteCode5, aDate.SurveyDate.strftime("%Y-%m-%d"), aDate.txtPointsPath))

                    # Any one survey fails then the minimum surface could be incorrect. Abort this site.
                    self.Ignore = True
                    return False

        # If got to here then all surveys validated
        return True

def LoadSandbarData(dirTopoFolder, xmlSites):
    """
    :param dirTopoFolder: The folder under which all the sandbar site topo folders exist. Typically ends with 'cordgrids'
    :param xmlSites: XML Element representing the Sites collection in the input XML file
    :return: Dictionary of sandbar sites to be processed. Key is SiteID, value is SandbarSite object

    Note that the sandbar site ASCII grids are currently found using the 4 digit site identifiers. This is how
    GCMRC currently stores them. e.g. ...\corgrids\003Lcorgrids But the goal is to improve this structure
    and enforce all sandbar data to be stored using 5 digit identifiers. The code below will need changing
    when this change is made.
    """

    log = Logger("Load Sandbars")

    dSites = {}

    nSurveyCount = 0
    nAnalysisCount = 0
    nMinSurfaceCount = 0

    for siteTag in xmlSites.iterfind("Site"):
        bAllSurveysPresent = True
        siteCode4 = siteTag.attrib["code4"]
        #print('dirTopoFolder', dirTopoFolder) # remove
        #print(os.listdir(os.getcwd() + os.sep + dirTopoFolder)) # remove
        dirSurveyFolder = os.path.join(dirTopoFolder, siteCode4 + "corgrids")
        #dirSurveyFolder = os.getcwd() + os.sep + dirTopoFolder + os.sep + siteCode4 + 'corgrids'
        #print('dirSurveyFolder', dirSurveyFolder) # remove
        #print(os.listdir(dirSurveyFolder))
        if os.path.isdir(dirSurveyFolder):
            sandbarSite = SandbarSite(siteCode4 \
                                    , siteTag.attrib["code5"] \
                                    , int(siteTag.attrib["id"]) \
                                    , float(siteTag.attrib["stagedisa"]) \
                                    , float(siteTag.attrib["stagedisb"]) \
                                    , float(siteTag.attrib["stagedisc"]) \
                                    , dirSurveyFolder)

            # Add the site to the main dictionary of sandbar sites
            dSites[int(siteTag.attrib["id"])] = sandbarSite

            # Load all the child surveys for this site
            for surveyTag in siteTag.iterfind("Surveys//Survey"):

                surveyDate = datetime.strptime(surveyTag.attrib["date"], "%Y-%m-%d")

                # Get the path to the ASCII points TXT file. The actual files have mixed case.
                txtPointsPath = os.path.join(sandbarSite.inputsSurveyFolder,
                                             "{0}_{1:%y%m%d}_grid.txt".format(sandbarSite.getNumericSiteCode(),
                                                                              surveyDate))

                txtPointsPath_Corrected = SandbarSurvey.getfile_insensitive(txtPointsPath)

                if txtPointsPath_Corrected:
                    nSurveyCount += 1
                    surveyID = int(surveyTag.attrib["id"])
                    isAnalysis = surveyTag.attrib["analysis"].lower() == 'true'
                    isMinSurface = surveyTag.attrib["minimum"].lower() == 'true'

                    if isAnalysis:
                        nAnalysisCount += 1

                    if isMinSurface:
                        nMinSurfaceCount +=1

                    sandbarSurvey = SandbarSurvey.SandbarSurvey(surveyID, surveyDate, txtPointsPath_Corrected, isAnalysis, isMinSurface)
                    sandbarSite.surveyDates[surveyID] = sandbarSurvey

                    # Load all the child sections that were collected during this survey
                    for sectionTag in surveyTag.iterfind("Sections//Section"):

                        sectionID = int(sectionTag.attrib["id"])
                        sectionTypeID = int(sectionTag.attrib["sectiontypeid"])
                        sandbarSurvey.surveyedSections[sectionTypeID] = SandbarSurveySection(sectionID,sectionTypeID, sectionTag.attrib["sectiontype"])

                else:
                    bAllSurveysPresent = False
                    log.warning("Missing txt file for site {0} at {1}".format(siteCode4, txtPointsPath))

            if not bAllSurveysPresent:
                log.warning("One or more survey txt files missing for site {0}. This site will not be processed.".format(siteCode4))

        else:
            log.warning("Missing folder for site {0} at {1}. This site will not be processed.".format(siteCode4, dirSurveyFolder))

    log.info("{0} sandbar sites loaded from input XML.".format(len(dSites)) )
    log.info("{0} total surveys loaded from the input XML. {1} for analysis and {2} for minimum surface.".format(nSurveyCount, nAnalysisCount, nMinSurfaceCount))

    return dSites

def getRasterTXTFilePath(dirTopLevelFolder, dirInputASCIIGrids, aSite, dtSurveyDate):
    """

    :param dirTopLevelFolder:
    :param dirInputASCIIGrids:
    :param aSite:
    :param dtSurveyDate:
    :return:
    """
    txtPath = os.path.join(dirTopLevelFolder, dirInputASCIIGrids, aSite.siteCode + "corgrids", "{0}_{1:%y%m%d}_grid.txt".format(aSite.getNumericSiteCode(), dtSurveyDate))
    casePath = "" # getfile_insensitive(txtPath)

    if casePath and os.path.isfile(casePath):
        return casePath
    else:
        return None
