# Copyright (c) 2017 Civic Knowledge. This file is licensed under the terms of the
# Revised BSD License, included in this distribution as LICENSE

"""
NBConvert preprocessors
"""

from traitlets import Integer, Unicode
from nbconvert.preprocessors import Preprocessor
from textwrap import dedent
from .magic import MetatabMagic
from nbformat.notebooknode import from_dict
from IPython.core.magic_arguments import (argument, magic_arguments,
                                          parse_argstring)


class ExtractInlineMetatabDoc(Preprocessor):
    """Extract the Inlined Metatab document"""

    doc = None

    def preprocess_cell(self, cell, resources, index):
        import re
        from metatab.generate import TextRowGenerator
        from metatab import MetatabDoc

        if cell['source'].startswith('%%metatab'):
            self.doc = MetatabDoc(TextRowGenerator("Declare: metatab-latest\n" +
                                                     re.sub(r'\%\%metatab.*\n', '',cell['source'])))

        return cell, resources

class ExtractFinalMetatabDoc(Preprocessor):
    """Extract the metatab document produced from the %mt_show_metatab magic"""

    from nbformat.notebooknode import NotebookNode

    doc = None

    def preprocess_cell(self, cell, resources, index):
        import re
        from metatab.generate import TextRowGenerator
        from metatab import MetatabDoc

        if cell['metadata'].get('mt_final_metatab'):
            if cell['outputs']:
                o = ''.join( e['text'] for e in cell['outputs'])

                self.doc = MetatabDoc(TextRowGenerator(o))

                # Give all of the sections their standard args, to make the CSV versions of the doc
                # prettier

                for name, s in self.doc.sections.items():
                    try:
                        s.args = self.doc.decl_sections[name.lower()]['args']
                    except KeyError:
                        pass

        return cell, resources


class RemoveMetatab(Preprocessor):
    """NBConvert preprocessor to remove the %metatab block"""

    def preprocess(self, nb, resources):
        import re

        out_cells = []

        mt_doc_name = 'mt_pkg'

        for cell in nb.cells:

            source = cell['source']

            if source.startswith('%%metatab'):

                lines = source.splitlines() # resplit to remove leading blank lines

                args = parse_argstring(MetatabMagic.metatab, lines[0].replace('%%metatab',''))

                cell.source = "%mt_open_package\n"
                cell.outputs = []
            else:
                cell.source = re.sub(r'\%mt_[^\n]+\n', '', source)

            out_cells.append(cell)

        nb.cells = out_cells

        return nb, resources

class RemoveMagics(Preprocessor):
    """Remove line magic lines, or entire cell magic cells"""

    def preprocess(self, nb, resources):
        import re

        for i, cell in enumerate(nb.cells):


            if re.match(r'^\%\%', cell.source):
                cell.source = ''
            else:
                cell.source = re.sub(r'\%[^\n]+\n?', '', cell.source)

        return nb, resources

class NoShowInput(Preprocessor):
    """NBConvert preprocessor to add hide_input metatab to cells, except to cells that have either
     an %mt_showinput magic, or a 'show' tag """

    def preprocess(self, nb, resources):
        import re

        out_cells = []

        for cell in nb.cells:

            #  Code cells aren't displayed at all, unless it starts with
            # a '%mt_showinput' magic, which is removed

            if cell['cell_type'] == 'code':

                source = cell['source']

                tags = cell['metadata'].get('tags',[])

                if source.startswith('%mt_showinput') or 'show' in tags:
                    cell['source'] = re.sub(r'\%mt_showinput','',source)
                else:
                    cell['metadata']['hide_input'] = True

            out_cells.append(cell)

        nb.cells = out_cells

        return nb, resources

class ExtractMetatabTerms(Preprocessor):
    """Look for tagged markdown cells and use the value to set some metatab doc terms"""

    terms = None

    def preprocess_cell(self, cell, resources, index):

        if not self.terms:
            self.terms = []

        if cell['cell_type'] == 'markdown':

            tags = cell['metadata'].get('tags', [])

            if 'Title' in tags:
                self.terms.append(('Root.Title', cell.source.strip().replace('#', '')))

            elif 'Description' in tags:
                self.terms.append(('Root.Description',cell.source.strip() ))

        return cell, resources


class AddEpilog(Preprocessor):
    """Add a final cell that writes the Metatab file, materializes datasets, etc.  """

    pkg_dir = Unicode(help='Metatab package Directory').tag(config=True)

    def preprocess(self, nb, resources):
        import re

        nb.cells.append(from_dict({
            'cell_type': 'code',
            'outputs': [],
            'metadata': {'mt_materialize' : True},
            'execution_count': None,
            'source': dedent("""
            %mt_materialize {pkg_dir}
            """.format(pkg_dir=self.pkg_dir))
        }))

        nb.cells.append(from_dict({
            'cell_type': 'code',
            'outputs': [],
            'metadata': {'mt_final_metatab': True},
            'execution_count': None,
            'source': dedent("""
            %mt_show_metatab

            """.format(pkg_dir=self.pkg_dir))
        }))

        return nb, resources