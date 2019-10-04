# Copyright (C) 2017-2019 Ronald E. Robertson <rer@ronalderobertson.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from . import webutils
from .component_classifier import classify_type
from .component_parsers import type_functions
from .component_parsers.footer import extract_footer
from . import logger
log = logger.Logger().start(__name__)

import traceback
from bs4 import BeautifulSoup

def parse_query(soup):
    """Parse query from title of html soup"""
    title = str(soup.html.find('title'))
    return webutils.strip_html_tags(title).split(" - ")[0]

def parse_lang(soup):
    """Parse language from html tags"""
    try:
        return soup.find('html').attrs['lang']
    except Exception:
        return None

def get_component_parser(cmpt_type, cmpt_funcs=type_functions):
    """Returns the parser for a given component type"""
    return cmpt_funcs[cmpt_type] if cmpt_type in cmpt_funcs else None

def extract_components(soup, include_ads=True):
    """Extract SERP components
    
    Args:
        soup (bs4): BeautifulSoup SERP
        include_ads (bool): Extract ads, defaults to True
    
    Returns:
        list: a rank ordered top-to-bottom and left-to-right list of 
             (component location, component soup) tuples
    """

    cmpts = []

    # Top Ads
    if include_ads:
        ads = soup.find('div', {'id':'tads'})
        if ads: 
            cmpts.append(('ad', ads))

    # Main results column
    column = [('main', r) for r in soup.find_all('div', {'class':'bkWMgd'})]
    # Hacky fix removing named Twitter component without content, possible G error
    # Another fix for empty components, e.g. - <div class="bkWMgd"></div>
    filter_text = ['Twitter Results', '']
    column = [(cloc, c) for cloc, c in column if c.text not in filter_text]
    cmpts.extend(column)

    # Bottom Ads
    if include_ads:
        ads = soup.find('div', {'id':'tadsb'})
        if ads:
            cmpts.append(('ad', ads))

    # Footer results
    footer = extract_footer(soup)
    if footer:
        cmpts.append(('footer', footer))

    return cmpts

def parse_component(cmpt, cmpt_type='', cmpt_rank=0):
    """Parse a SERP component
    
    Args:
        cmpt (bs4 object): A parsed SERP component
        cmpt_type (str, optional): The type of component it is
        cmpt_rank (int, optional): The rank the component was found
    
    Returns:
        dict: The parsed results and/or subresults
    """
    parsed_cmpt = [{'type':'unknown', 'sub_rank':0, 'cmpt_rank':cmpt_rank}]

    cmpt_type = cmpt_type if cmpt_type else classify_type(cmpt)
    if not cmpt_type or cmpt_type == 'unknown':
        # Unknown component
        return parsed_cmpt
    if not type_functions[cmpt_type]:
        # Named component but no function
        parsed_cmpt[0]['type'] = cmpt_type
        return parsed_cmpt

    try:
        parser = get_component_parser(cmpt_type)
        parsed_cmpt = parser(cmpt)

        # Add cmpt rank to parsed
        if isinstance(parsed_cmpt, list):
            for sub_rank, sub in enumerate(parsed_cmpt):
                sub.update({'sub_rank':sub_rank, 'cmpt_rank':cmpt_rank})
        else:
            parsed_cmpt.update({'sub_rank':0, 'cmpt_rank':cmpt_rank})

    except Exception:
        log.exception('Parsing Exception')
        parsed_cmpt = [{'type':cmpt_type, 'cmpt_rank':cmpt_rank, 
                        'error':traceback.format_exc()}]
    return parsed_cmpt

def parse_serp(serp, serp_id=None, verbose=False, make_soup=False):
    """Parse a Search Engine Result Page (SERP)
    
    Args:
        serp (html): raw SERP HTML or BeautifulSoup
        serp_id (str, optional): A SERP-level key, hash generated by default
        verbose (bool, optional): Log details about each component parse
    
    Returns:
        list: A list of parsed results ordered top-to-bottom and left-to-right
    """

    soup = webutils.make_soup(serp) if make_soup else serp
    assert type(soup) is BeautifulSoup, 'Input must be BeautifulSoup'
    cmpts = extract_components(soup)

    parsed = []
    log.info(f'Parsing SERP {serp_id}')
    for cmpt_rank, (cmpt_loc, cmpt) in enumerate(cmpts):
        cmpt_type = classify_type(cmpt) if cmpt_loc == 'main' else cmpt_loc
        if verbose: 
            log.info(f'{cmpt_rank} | {cmpt_type}')
        parsed_cmpt = parse_component(cmpt, cmpt_type=cmpt_type, cmpt_rank=cmpt_rank)
        assert isinstance(parsed_cmpt, list), \
            f'Parsed component must be list: {parsed_cmpt}'
        parsed.extend(parsed_cmpt)

    for serp_rank, p in enumerate(parsed):
        p['qry'] = parse_query(soup)
        p['lang'] = parse_lang(soup)
        p['serp_id'] = serp_id
        p['serp_rank'] = serp_rank
    return parsed
