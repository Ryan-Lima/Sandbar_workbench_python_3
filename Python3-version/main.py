import os
import sys
import argparse
from logger import Logger

from AnalysisBins import LoadAnalysisBins
from SandbarSite import LoadSandbarData
from SectionTypes import LoadSectionTypes

from ComputationExtents import ComputationExtents
from IncrementalAnalysis import RunIncrementalAnalysis
from BinnedAnalysis import RunBinnedAnalysis
from RasterPreparation import RasterPreparation

from ConfigLoader import loadConfig

# Initialize logger.
log = Logger()

if 'DEBUG' in os.environ:
    import pydevd
    pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)

def main(config):

    log = Logger("Initializing")

    # Load a dictionary of SandbarSites and their surveys from the workbench
    # database for the sites that need to be processed.
    dSectionTypes = LoadSectionTypes(config["SectionTypes"])
    dAnalysisBins = LoadAnalysisBins(config["AnalysisBins"])
    lSites = LoadSandbarData(config["TopLevelFolder"], config["Sites"])

    # Load the ShapeFile containing computational extent polygons for sandbar sites
    # Validate all sites have polygon extent features in this ShapeFile.
    #print('config["CompExtentShpPath"]',config["CompExtentShpPath"])
    CompExtentShp = ComputationExtents(config["CompExtentShpPath"], config["srsEPSG"])
    CompExtentShp.ValidateSiteCodes(lSites)

    # setMethod is a totally
    # Create the DEM rasters and then clip them to the sandbar sections
    RasterPreparation(lSites, config["AnalysisFolder"], config["CSVCellSize"], config["RasterCellSize"],
                      config["ResampleMethod"], config["srsEPSG"], config["ReUseRasters"], config["GDALWarp"],
                      dSectionTypes, CompExtentShp)

    # prepare result file paths
    sIncResultFilePath = os.path.join(config["AnalysisFolder"], config["IncrementalResults"])
    sBinResultFilePath = os.path.join(config["AnalysisFolder"], config["BinnedResults"])

    # Run the analyses
    RunIncrementalAnalysis(lSites, config["ElevationBenchmark"], config["ElevationIncrement"], config["RasterCellSize"], sIncResultFilePath)
    RunBinnedAnalysis(lSites, dAnalysisBins, config["RasterCellSize"],sBinResultFilePath)

    log.info("Sandbar analysis process complete.")

"""
This function handles the argument parsing and calls our main function
"""
if __name__ == '__main__':
    #parse command line options
    parser = argparse.ArgumentParser()
    parser.add_argument('input_xml',
                        help = 'Path to the input XML file.',
                        type = str)
    parser.add_argument('--verbose',
                        help = 'Get more information in your logs.',
                        action='store_true',
                        default=False )
    args = parser.parse_args()

    # Load the XML into a simple dictionary
    conf = loadConfig(args.input_xml)

    log = Logger("Program")
    log.setup(logRoot=conf["AnalysisFolder"],
              xmlFilePath=conf["Log"],
              verbose=args.verbose,
              config=conf)

    log.debug("Config file", conf)

    try:
        # Now kick things off
        log.info("Starting Sandbar script with: input_xml: {0}".format(args.input_xml))
        main(conf)
    except AssertionError as e:
        log.error("Assertion Error", e)
        sys.exit(0)
    except Exception as e:
        log.error('Unexpected error: {0}'.format(sys.exc_info()[0]), e)
        raise
        sys.exit(0)
