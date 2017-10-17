#!/usr/bin/env python2

# This file is part of Archivematica.
#
# Copyright 2010-2013 Artefactual Systems Inc. <http://artefactual.com>
#
# Archivematica is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Archivematica is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Archivematica.  If not, see <http://www.gnu.org/licenses/>.

# @package Archivematica
# @subpackage archivematicaClientScript
# @author Joseph Perry <joseph@artefactual.com>

from __future__ import print_function
import os
import pprint
import sys
import shutil

from lxml import etree
import metsrw

# archivematicaCommon
from custom_handlers import get_script_logger
import archivematicaFunctions


logger = get_script_logger("archivematica.mcp.client.restructureBagAIPToSIP")


NORMATIVE_STRUCTMAP_LABEL = 'Normative Directory Structure'


def _move_file(src, dst, exit_on_error=True):
    print('Moving', src, 'to', dst)
    try:
        shutil.move(src, dst)
    except IOError:
        print('Could not move', src)
        if exit_on_error:
            raise


def div_el_to_dir_paths(div_el, parent='', include=True):
    """Recursively extract the list of filesystem directory paths encoded in
    <mets:div> element ``div_el``.
    """
    paths = []
    path = parent
    dir_name = div_el.get('LABEL')
    if parent == '' and dir_name in ('metadata', 'submissionDocumentation'):
        return []
    if include:
        path = os.path.join(parent, dir_name)
        paths.append(path)
    for sub_div_el in div_el.findall('mets:div[@TYPE="Directory"]',
                                     metsrw.NAMESPACES):
        paths += div_el_to_dir_paths(sub_div_el, parent=path)
    return paths


def reconstruct_empty_directories(mets_file_path, objects_path):
    """Reconstruct in objects/ path ``objects_path`` the empty directories
    documented in METS file ``mets_file_path``.
    :param str mets_file_path: absolute path to an AIP/SIP's METS file.
    :param str objects_path: absolute path to an AIP/SIP's objects/ directory
        on disk.
    """
    if (not os.path.isfile(mets_file_path) or
            not os.path.isdir(objects_path)):
        logger.info('Unable to construct empty directories, either because'
                    ' there is no METS file at {} or because there is no'
                    ' objects/ directory at {}'.format(mets_file_path,
                                                       objects_path))
        return
    doc = etree.parse(mets_file_path, etree.XMLParser(remove_blank_text=True))
    logical_struct_map_el = doc.find(
        'mets:structMap[@TYPE="logical"][@LABEL="{}"]'.format(
            NORMATIVE_STRUCTMAP_LABEL),
        metsrw.NAMESPACES)
    if logical_struct_map_el is None:
        logger.info('Unable to locate a logical structMap labelled {}. Aborting'
                    ' attempt to reconstruct empty directories.'.format(
                        NORMATIVE_STRUCTMAP_LABEL))
        return
    root_div_el = logical_struct_map_el.find(
        'mets:div/mets:div[@LABEL="objects"]', metsrw.NAMESPACES)
    if root_div_el is None:
        logger.info('Unable to locate a logical structMap labelled {}. Aborting'
                    ' attempt to reconstruct empty directories.'.format(
                        NORMATIVE_STRUCTMAP_LABEL))
        return
    paths = div_el_to_dir_paths(root_div_el, include=False)
    logger.info('paths extracted from METS file:')
    logger.info(pprint.pformat(paths))
    for path in paths:
        path = os.path.join(objects_path, path)
        if not os.path.isdir(path):
            os.makedirs(path)


if __name__ == '__main__':

    sip_path = sys.argv[1]

    # Move everything out of data directory
    for item in os.listdir(os.path.join(sip_path, 'data')):
        src = os.path.join(sip_path, 'data', item)
        dst = os.path.join(sip_path, item)
        _move_file(src, dst)

    os.rmdir(os.path.join(sip_path, 'data'))

    # Move metadata and logs out of objects if they exist
    objects_path = os.path.join(sip_path, 'objects')
    src = os.path.join(objects_path, 'metadata')
    dst = os.path.join(sip_path, 'metadata')
    _move_file(src, dst, exit_on_error=False)

    src = os.path.join(objects_path, 'logs')
    dst = os.path.join(sip_path, 'logs')
    _move_file(src, dst, exit_on_error=False)

    # Move anything unexpected to submission documentation
    # Leave objects, metadata, etc
    # Original METS ends up in submissionDocumentation
    subm_doc_path = os.path.join(
        sip_path, 'metadata', 'submissionDocumentation')
    os.makedirs(subm_doc_path)
    mets_file_path = None
    for item in os.listdir(sip_path):
        # Leave SIP structure
        if item in archivematicaFunctions.OPTIONAL_FILES + archivematicaFunctions.REQUIRED_DIRECTORIES:
            continue
        src = os.path.join(sip_path, item)
        dst = os.path.join(subm_doc_path, item)
        if item.startswith('METS.') and item.endswith('.xml'):
            mets_file_path = dst
        _move_file(src, dst)
    if mets_file_path:
        reconstruct_empty_directories(mets_file_path, objects_path)
    else:
        logger.info('Unable to reconstruct empty directories: no METS file'
                    ' could be found in {}'.format(sip_path))
    archivematicaFunctions.create_structured_directory(sip_path, manual_normalization=True, printing=True)
