from logger import Logger

def LoadSectionTypes(sectionTypesTree):
    log = Logger("Load Sections")
    dSections = {}
    for typeTag in sectionTypesTree.iterfind('Section'):
        dSections[int(typeTag.attrib["id"])] = typeTag.attrib["title"]

    assert len(dSections) > 0, "{0} active section types.".format(len(dSections))

    log.info("{0} section types loaded from the input XML file.".format(len(dSections)))

    return dSections