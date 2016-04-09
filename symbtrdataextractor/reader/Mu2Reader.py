import csv
import warnings
from ..MetadataExtractor import MetadataExtractor
from SymbTrReader import SymbTrReader


class Mu2Reader(SymbTrReader):
    def __init__(self):
        """
        Class constructor
        """
        pass

    @classmethod
    def read_mu2_score(cls, score_file, symbtr_name=None):
        """
        Reader method for the SymbTr-mu2 scores. This method is not
        implemented yet.

        Parameters
        ----------
        score_file : str
            The path of the SymbTr score
        symbtr_name : str, optional
            The name of the score in SymbTr naming convention
            (makam--form--usul--name--composer).
        Returns
        ----------
        NotImplemented
        """
        if symbtr_name is None:
            symbtr_name = Mu2Reader.get_symbtr_name_from_filepath(score_file,
                                                                  symbtr_name)

        # TODO
        return NotImplemented

    @staticmethod
    def read_mu2_header(score_file, symbtr_name=None):
        """
        Reads the metadata in the header of the SymbTr-mu2 scores.

        Parameters
        ----------
        score_file : str
            The path of the SymbTr score
        symbtr_name : str, optional
            The name of the score in SymbTr naming convention
            (makam--form--usul--name--composer).
        Returns
        ----------
        dict
            A dictionary storing the metadata extracted from the header
        list of str
            The names of the columns in the mu2 file
        bool
            True if the metadata in the mu2 header is valid/consistent,
            False otherwise
        """
        if symbtr_name is None:
            symbtr_name = Mu2Reader.get_symbtr_name_from_filepath(score_file,
                                                                  symbtr_name)

        makam_slug = symbtr_name.split('--')[0]

        with open(score_file, "rb") as f:
            reader = csv.reader(f, delimiter='\t')

            header_row = [unicode(cell, 'utf-8') for cell in next(reader,
                                                                  None)]

            header = dict()
            is_tempo_unit_valid = True
            is_key_sig_valid = True
            for row_temp in reader:
                row = [unicode(cell, 'utf-8') for cell in row_temp]
                code = int(row[0])
                if code == 50:
                    is_key_sig_valid = Mu2Reader.read_makam_key_signature_row(
                        header, is_key_sig_valid, makam_slug, row, symbtr_name)
                elif code == 51:
                    header['usul'] = {'mu2_name': row[7],
                                      'mertebe': int(row[3]),
                                      'number_of_pulses': int(row[2])}
                elif code == 52:
                    is_tempo_unit_valid = Mu2Reader._read_tempo_row(
                        row, symbtr_name, header, is_tempo_unit_valid)
                elif code == 56:
                    header['usul']['subdivision'] = {'mertebe': int(row[3]),
                                                     'number_of_pulses':
                                                         int(row[2])}
                elif code == 57:
                    header['form'] = {'mu2_name': row[7]}
                elif code == 58:
                    header['composer'] = {'mu2_name': row[7]}
                elif code == 59:
                    header['lyricist'] = {'mu2_name': row[7]}
                elif code == 60:
                    header['title'] = {'mu2_title': row[7]}
                elif code == 62:
                    header['genre'] = 'folk' if row[7] == 'E' else 'classical'
                elif code == 63:
                    header['notation'] = row[7]
                elif code in range(50, 64):
                    warnings.warn('   Unparsed code: ' + ' '.join(row))
                else:  # end of header
                    break

        # get the metadata
        slugs = MetadataExtractor.get_slugs(symbtr_name)
        Mu2Reader._add_attribute_slug_to_header(header, slugs, 'makam')
        Mu2Reader._add_attribute_slug_to_header(header, slugs, 'form')
        Mu2Reader._add_attribute_slug_to_header(header, slugs, 'usul')

        header['title']['symbtr_slug'] = slugs['name']
        header['composer']['symbtr_slug'] = slugs['composer']

        # validate the header content
        is_attr_meta_valid = MetadataExtractor.validate_makam_form_usul(
            header, symbtr_name)

        is_header_valid = (is_tempo_unit_valid and is_attr_meta_valid and
                           is_key_sig_valid)

        return header, header_row, is_header_valid

    @staticmethod
    def read_makam_key_signature_row(header, is_key_sig_valid, makam_slug, row,
                                     symbtr_name):
        header['makam'] = {'mu2_name': row[7]}
        header['key_signature'] = row[8].split('/')
        if not header['key_signature'][0]:
            header['key_signature'] = []

        # validate key signature
        is_key_sig_valid = is_key_sig_valid and MetadataExtractor. \
            validate_key_signature(header['key_signature'],
                                   makam_slug, symbtr_name)
        return is_key_sig_valid

    @staticmethod
    def _read_tempo_row(row, symbtr_name, header, is_tempo_unit_valid):
        try:
            header['tempo'] = {'value': int(row[4]),
                               'unit': 'bpm'}
        except ValueError:
            # the bpm might be a float for low tempo
            header['tempo'] = {'value': float(row[4]),
                               'unit': 'bpm'}

        if not int(row[3]) == header['usul']['mertebe']:
            if not header['usul']['mu2_name'] == '[Serbest]':
                # ignore
                warn_str = '    ' + symbtr_name + \
                           ': Mertebe and tempo unit are ' \
                           'different!'
                warnings.warn(warn_str)
                is_tempo_unit_valid = False

        return is_tempo_unit_valid

    @staticmethod
    def _add_attribute_slug_to_header(header, slugs, attr_name):
        header[attr_name]['symbtr_slug'] = slugs[attr_name]
        header[attr_name]['attribute_key'] = \
            MetadataExtractor.get_attribute_key(
                header[attr_name]['symbtr_slug'], attr_name)
