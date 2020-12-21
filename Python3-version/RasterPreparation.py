import os.path
from logger import Logger

def RasterPreparation(dSites, analysisFolder, csvCellSize, rasterCellSize, resampleMethod, srsEPSG, reuseRasters, gdalWarp,
                      sectionTypes, compExtentShp):

    log = Logger("Raster Prep")

    for siteID, site in dSites.items():

        log.info("Site {0}: Starting raster preparation...".format(site.siteCode5))

        # Verify that ALL text files for all surveys at this site are correctly formatted
        site.verifyTXTFileFormat()

        # Skip the site if it failed to find computational extent
        if site.Ignore:
            continue

        # Make a subfolder in the output workspace for this survey
        surveyFolder = os.path.join(analysisFolder, site.siteCode5)
        if not os.path.exists(surveyFolder):
            os.makedirs(surveyFolder)

        assert os.path.exists(surveyFolder), "Failed to generate output folder for site {0} at {1}".format(site.siteCode5, surveyFolder)

        # Convert the TXT files to GeoTIFFs
        site.GenerateDEMRasters(surveyFolder, csvCellSize, rasterCellSize, resampleMethod, srsEPSG, reuseRasters)
        site.ClipDEMRastersToSections(gdalWarp, surveyFolder, sectionTypes, compExtentShp, reuseRasters)

        elevation8k = site.getStage(8000)
        elevation25k = site.getStage(25000)
        log.info("Site {0}: Raster preparation is complete. Elevation at 8K is {1:.3f} and 25K is {2:.3f}".format(site.siteCode5, elevation8k, elevation25k))

    log.info("Raster preparation is complete for all {0} sites.".format(len(dSites)))