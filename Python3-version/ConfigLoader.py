import os
import xml.etree.ElementTree as ET

def loadConfig(xmlFile):
    config = {}
    tree = ET.parse(xmlFile)
    root = tree.getroot()

    # The analysis folder is the same location as the input.xml
    config['AnalysisFolder'] = os.path.dirname(xmlFile)

    meta = root.find('MetaData')
    # Just put the whole meta into the config object
    config['MetaData'] = meta

    tags = root.find('Outputs')
    for theTag in tags:
        config[theTag.tag] = theTag.text

    tags = root.find('Inputs')
    # For inputs and outputs create a dictionary
    for theTag in tags:
        if theTag.tag == "Sites" \
            or theTag.tag == "SectionTypes" \
            or theTag.tag == "AnalysisBins":

            config[theTag.tag] = theTag

        elif theTag.tag == "CSVCellSize" \
            or theTag.tag == "RasterCellSize" \
            or theTag.tag == "ElevationIncrement" \
            or theTag.tag == "ElevationBenchmark":

            config[theTag.tag] = float(theTag.text)

        elif theTag.tag == "ReUseRasters":
            config['ReUseRasters'] = theTag.text.upper() == "TRUE"

        else:
            config[theTag.tag] = theTag.text
    return config
