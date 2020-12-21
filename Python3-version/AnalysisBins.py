from logger import Logger


class AnalysisBin:

    def __init__(self, binID, title, lowerDischarge, upperDischarge):
        self.binID = binID
        self.title = title
        self.lowerDischarge = lowerDischarge
        self.upperDischarge = upperDischarge

    def __repr__(self):
        return "AnalysisBin: {0} - {1} lower: {2} upper: {3}".format(self.binID, self.title, self.lowerDischarge, self.upperDischarge)


def LoadAnalysisBins(analysisBinElement):

    dAnalysisBins = {}
    log = Logger("Load Bins")

    # Note that lower or upper Discharge may be NULL
    for binTag in analysisBinElement.iterfind('Bin'):
        
        fLowerDischarge = None
        if len(binTag.attrib["lower"]) > 0:
            fLowerDischarge = float(binTag.attrib["lower"])

        fUpperDischarge = None
        if len(binTag.attrib["upper"]) > 0:
            fUpperDischarge = float(binTag.attrib["upper"])

        dAnalysisBins[int(binTag.attrib["id"])] = AnalysisBin(int(binTag.attrib["id"]), binTag.attrib["title"], fLowerDischarge, fUpperDischarge)

    assert len(dAnalysisBins) > 0, "{0} analysis bins loaded from the input XML file.".format(len(dAnalysisBins))
    log.info("{0} analysis bins loaded from the input XML file.".format(len(dAnalysisBins)))

    log.debug("Analysis Bins:", dAnalysisBins, "original Element:", analysisBinElement)

    return dAnalysisBins
