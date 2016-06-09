import sublime
import sublime_plugin
import re
import pprint
import sys
import os.path
sys.path.append(os.path.join(os.path.dirname(__file__),'lib'))
# third party libraries
from bs4 import BeautifulSoup

# for dbug
pp = pprint.PrettyPrinter(indent=4)

pattern_reference_link = re.compile(r'\[.+?\]$') # [Heading][my-id]
pattern_link = re.compile(r'\[(.+?)\]\(.+?\)')  # [link](http://www.sample.com/)
pattern_ex_id = re.compile(r'\{#.+?\}$')         # [Heading]{#my-id}
pattern_tag = re.compile(r'<.*?>')
pattern_anchor = re.compile(r'<a\s+name="[^"]+"\s*>\s*</a>')
pattern_toc_tag_start = re.compile(r'<!-- *')
pattern_toc_tag_end = re.compile(r'-->')

pattern_h1_h2_equal_dash = "^.*?(?:(?:\r\n)|\n|\r)(?:-+|=+)$"

TOCTAG_START = "<!-- MarkdownTOC -->"
TOCTAG_END = "<!-- /MarkdownTOC -->"

class MarkdowntocInsert(sublime_plugin.TextCommand):

    def run(self, edit):

        if not self.find_tag_and_insert(edit):
            sels = self.view.sel()
            for sel in sels:
                attrs = self.get_settings()

                # add TOCTAG
                toc = TOCTAG_START + "\n"
                toc += "\n"
                toc += self.get_toc(attrs, sel.end(), edit)
                toc += "\n"
                toc += TOCTAG_END + "\n"

                self.view.insert(edit, sel.begin(), toc)
                log('inserted TOC')

        # TODO: process to add another toc when tag exists

    def get_toc_open_tag(self):
        search_results = self.view.find_all(
            "^<!-- MarkdownTOC .*-->\n",
            sublime.IGNORECASE)
        search_results = self.remove_items_in_codeblock(search_results)

        toc_open_tags = []
        for toc_open in search_results:
            if 0 < len(toc_open):

                toc_open_tag = {"region": toc_open}

                # settings in user settings
                settings_user = self.get_settings()

                # settings in tag
                tag_str = self.view.substr(toc_open)
                settings_tag = self.get_attibutes_from(tag_str)

                # merge
                toc_open_tag.update(settings_user)
                toc_open_tag.update(settings_tag)

                toc_open_tags.append(toc_open_tag)

        return toc_open_tags

    def get_toc_close_tag(self, start):
        close_tags = self.view.find_all("^" + TOCTAG_END + "\n")
        close_tags = self.remove_items_in_codeblock(close_tags)
        for close_tag in close_tags:
            if start < close_tag.begin():
                return close_tag

    def find_tag_and_insert(self, edit):
        """Search MarkdownTOC comments in document"""
        toc_starts = self.get_toc_open_tag()
        for dic in toc_starts:

            toc_start = dic["region"]
            if 0 < len(toc_start):

                toc_close = self.get_toc_close_tag(toc_start.end())

                if toc_close:
                    toc = self.get_toc(dic, toc_close.end(), edit)
                    tocRegion = sublime.Region(
                        toc_start.end(), toc_close.begin())
                    if toc:
                        self.view.replace(edit, tocRegion, "\n" + toc + "\n")
                        log('refresh TOC content')
                        return True
                    else:
                        self.view.replace(edit, tocRegion, "\n")
                        log('TOC is empty')
                        return False
        log('cannot find TOC tags')
        return False

    # TODO: add "end" parameter
    def get_toc(self, attrs, begin, edit):

        # Search headings in docment
        pattern_hash = "^#+?[^#]"
        headings = self.view.find_all(
            "%s|%s" % (pattern_h1_h2_equal_dash, pattern_hash))

        headings = self.remove_items_in_codeblock(headings)

        if len(headings) < 1:
            return False

        headingItems = []  # [HeadingItem,...]
        for heading in headings:
            if begin < heading.end():

                lines = self.view.lines(heading)
                if len(lines) == 1:
                    # handle hash headings, ### chapter 1
                    r = sublime.Region(
                        heading.end(), self.view.line(heading).end())
                    headingItem = HeadingItem()
                    headingItem.h = heading.size() - 1
                    headingItem.text = self.view.substr(r)
                    headingItem.position = heading.begin()
                    headingItems.append(headingItem)
                elif len(lines) == 2:
                    # handle - or + headings, Title 1==== section1----
                    text = self.view.substr(lines[0])
                    if text.strip():
                        headingItem = HeadingItem()
                        headingItem.h = 1 if (
                            self.view.substr(lines[1])[0] == '=') else 2
                        headingItem.text = text
                        headingItem.position = heading.begin()
                        headingItems.append(headingItem)

        if len(headingItems) < 1:
            return ''

        # Shape TOC  ------------------
        headingItems = self.format(headingItems)

        # Depth limit  ------------------
        _depth = int(attrs['depth'])
        if 0 < _depth:
            headingItems = list(filter((lambda i: i.h <= _depth), headingItems))

        # Create TOC  ------------------
        toc = ''
        _ids = []

        for item in headingItems:
            _id = None
            _indent = item.h - 1
            _text = item.text
            _text = pattern_tag.sub('', _text) # remove html tags
            _text = _text.rstrip() # remove end space

            # Ignore links: e.g. '[link](http://sample.com/)' -> 'link'
            _text = pattern_link.sub('\\1', _text)

            # Add indent
            for i in range(_indent):
                _prefix = attrs['indent']
                # Support escaped characters like '\t'
                _prefix = _prefix.encode().decode('unicode-escape')
                toc += _prefix

            # Reference-style links: e.g. '# heading [my-anchor]'
            list_reference_link = list(pattern_reference_link.finditer(_text))

            # Markdown-Extra special attribute style: e.g. '# heading {#my-anchor}'
            match_ex_id = pattern_ex_id.search(_text)

            if len(list_reference_link):
                match = list_reference_link[-1]
                _text = _text[0:match.start()].replace('[','').replace(']','').rstrip()
                _id = match.group().replace('[','').replace(']','')
            elif match_ex_id:
                _text = _text[0:match_ex_id.start()].rstrip()
                _id = match_ex_id.group().replace('{#','').replace('}','')
            elif strtobool(attrs['autolink']):
                _id = self.replace_chars_in_id(_text.lower())
                _ids.append(_id)
                n = _ids.count(_id)
                if 1 < n:
                    _id += '-' + str(n-1)

            if attrs['style'] == 'unordered':
                list_prefix = '- '
            elif attrs['style'] == 'ordered':
                list_prefix = '1. '

            # escape brackets
            _text = _text\
                        .replace('(','\(')\
                        .replace(')','\)')\
                        .replace('[','\[')\
                        .replace(']','\]')

            if _id == None:
                toc += list_prefix + _text + '\n'
            elif attrs['bracket'] == 'round':
                toc += list_prefix + '[' + _text + '](#' + _id + ')\n'
            else:
                toc += list_prefix + '[' + _text + '][' + _id + ']\n'

            item.anchor_id = _id

        self.update_anchors(edit, headingItems, strtobool(attrs['autoanchor']))

        return toc

    def update_anchors(self, edit, headingItems, autoanchor):
        """Inserts, updates or deletes a link anchor in the line before each header."""
        v = self.view
        # Iterate in reverse so that inserts don't affect the position
        for item in reversed(headingItems):
            anchor_region = v.line(item.position - 1)  # -1 to get to previous line
            is_update = pattern_anchor.match(v.substr(anchor_region))
            if autoanchor:
                if is_update:
                    new_anchor = '<a name="{0}"></a>'.format(item.anchor_id)
                    v.replace(edit, anchor_region, new_anchor)
                else:
                    new_anchor = '\n<a name="{0}"></a>'.format(item.anchor_id)
                    v.insert(edit, anchor_region.end(), new_anchor)

            else:
                if is_update:
                    v.erase(edit, sublime.Region(anchor_region.begin(), anchor_region.end() + 1))

    def get_setting(self, attr):
        settings = sublime.load_settings('MarkdownTOC.sublime-settings')
        return settings.get(attr)

    def get_settings(self):
        """return dict of settings"""
        return {
            "depth":      self.get_setting('default_depth'),
            "autolink":   self.get_setting('default_autolink'),
            "bracket":    self.get_setting('default_bracket'),
            "autoanchor": self.get_setting('default_autoanchor'),
            "style":      self.get_setting('default_style'),
            "indent":     self.get_setting('default_indent')
        }

    def get_attibutes_from(self, tag_str):
        """return dict of settings from tag_str"""

        # convert TOC tag to HTML-like tag
        tag_str_html = pattern_toc_tag_start.sub("<", tag_str)
        tag_str_html = pattern_toc_tag_end.sub(">", tag_str_html)

        soup = BeautifulSoup(tag_str_html, "html.parser")

        return soup.find('markdowntoc').attrs

    def remove_items_in_codeblock(self, headingItems):

        codeblocks = self.view.find_all("^`{3,}[^`]*$")
        codeblockAreas = []
        i = 0
        while i < len(codeblocks)-1:
            area = Area()
            area.begin = codeblocks[i].begin()
            area.end   = codeblocks[i+1].begin()
            if area.begin and area.end:
                codeblockAreas.append(area)
            i += 2

        headingItems = [h for h in headingItems if is_out_of_areas(h.begin(), codeblockAreas)]
        return headingItems

    def replace_chars_in_id(self, _str):
        replacements = self.get_setting('id_replacements')
        # log(replacements)
        for _key in replacements:
            _substitute = _key
            _target_chars = replacements[_key]
            table = {}
            for char in _target_chars:
                table[ord(char)] = _substitute
            _str = _str.translate(table)
        return _str

    def format(self, headingItems):
        headings = []
        for item in headingItems:
            headings.append(item.h)
        # --------------------------

        # minimize diff between headings -----
        _depths = list(set(headings)) # sort and unique
        # replace with depth rank
        for i, item in enumerate(headings):
            headings[i] = _depths.index(headings[i])+1
        # ----- /minimize diff between headings

        # --------------------------
        for i, item in enumerate(headingItems):
            item.h = headings[i]
        return headingItems

# Search and refresh if it's exist

class MarkdowntocUpdate(MarkdowntocInsert):

    def run(self, edit):
        MarkdowntocInsert.find_tag_and_insert(self, edit)


class AutoRunner(sublime_plugin.EventListener):

    def on_pre_save(self, view):
        # limit scope
        root, ext = os.path.splitext(view.file_name())
        ext = ext.lower()
        if ext in [".md", ".markdown", ".mdown", ".mdwn", ".mkdn", ".mkd", ".mark"]:
            view.run_command('markdowntoc_update')

# Data Type

class HeadingItem:
    def __init__(self):
        self.h = None
        self.text = None
        self.position = None
        self.anchor_id = None

class Area:
    def __init__(self):
        self.begin = None
        self.end = None

# Util

def is_out_of_areas(num, areas):
    for area in areas:
        if area.begin < num and num < area.end:
            return False
    return True

def log(arg):
    arg = str(arg)
    sublime.status_message(arg)
    pp.pprint(arg)

def strtobool(val):
    """pick out from 'distutils.util' module"""
    if isinstance(val, str):
        val = val.lower()
        if val in ('y', 'yes', 't', 'true', 'on', '1'):
            return 1
        elif val in ('n', 'no', 'f', 'false', 'off', '0'):
            return 0
        else:
            raise ValueError("invalid truth value %r" % (val,))
    else:
        return bool(val)