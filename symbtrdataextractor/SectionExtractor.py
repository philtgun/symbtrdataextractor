from math import floor
from fileoperations.slugify_tr import slugify_tr
from . ScoreProcessor import ScoreProcessor
from . StructureLabeler import StructureLabeler
from . OffsetProcessor import OffsetProcessor
import warnings


class SectionExtractor(object):
    """

    """
    def __init__(self, lyrics_sim_thres=0.75, melody_sim_thres=0.75,
                 extract_all_labels=False, print_warnings=True):
        """
        Class constructor

        Parameters
        ----------
        lyrics_sim_thres : float[0, 1], optional
            The similarity threshold for the lyrics of two sections/phrases
            to be regarded as similar. (the default is 0.75)
        melody_sim_thres : float[0, 1], optional
            The similarity threshold for the melody of two sections/phrases
            to be regarded as similar. (the default is 0.75)
        extract_all_labels : bool, optional
            True to extract all labels in written in the lyrics field
            regardless they are a structural marking etc., False to only
            extract the lyrics. (the default is False)
        print_warnings : bool, optional
            True to display warnings, False otherwise. Note that the errors
            and the inconsistencies in the scores will be always displayed
            (the default is True)
        """
        self.extract_all_labels = extract_all_labels
        self.lyrics_sim_thres = lyrics_sim_thres
        self.melody_sim_thres = melody_sim_thres
        self.print_warnings = print_warnings

        self.offsetProcessor = OffsetProcessor(
            print_warnings=self.print_warnings)
        self.sectionLabeler = StructureLabeler(
            lyrics_sim_thres=self.lyrics_sim_thres,
            melody_sim_thres=self.melody_sim_thres)

    def from_txt_score(self, score, symbtrname):
        all_labels = ScoreProcessor.get_all_symbtr_labels()
        struct_lbl = all_labels if self.extract_all_labels else \
            ScoreProcessor.get_grouped_symbtr_labels()['structure']

        measure_start_idx, is_measure_start_valid = \
            self.offsetProcessor.find_measure_start_idx(score['offset'])

        # Check lyrics information
        if all(l == '' for l in score['lyrics']):
            # empty lyrics field; we cannot really do anything without
            # symbolic analysis
            sections = []
        else:
            sections = self._get_sections(score, struct_lbl)
            sections = self._locate_section_boundaries(
                sections, score, measure_start_idx)

            # the refine section names according to the lyrics, pitch and durs
            sections = self.sectionLabeler.label_structures(sections, score)

        sections_valid = self._validate_sections(
            sections, score, set(all_labels) - set(struct_lbl), symbtrname)
        valid_bool = sections_valid and is_measure_start_valid

        # map the python indices in start_note and end_note to SymbTr index
        for se in sections:
            se['start_note'] = score['index'][se['start_note']]
            se['end_note'] = score['index'][se['end_note']]

        return sections, valid_bool

    def from_musicxml_score(self, score):
        return NotImplemented

    def from_mu2_score(self, score):
        return NotImplemented

    @staticmethod
    def _get_sections(score, struct_lbl):
        sections = []
        for i, l in enumerate(score['lyrics']):
            if l in struct_lbl:  # note the explicit structures
                sections.append({'name': l, 'slug': slugify_tr(l),
                                 'start_note': i, 'end_note': [],
                                 'lyrics': ''})
            elif '  ' in l:  # lyrics end marker
                # lyrics will be updated in locate_section_boundaries
                sections.append({'name': u"VOCAL_SECTION",
                                 'slug': u"VOCAL_SECTION", 'start_note': [],
                                 'end_note': i, 'lyrics': ''})
        return sections

    def _locate_section_boundaries(self, sections, score, measure_start_idx):
        real_lyrics_idx = ScoreProcessor.get_true_lyrics_idx(
            score['lyrics'], score['duration'])

        start_note_idx = self._section_start_note_idx(score, sections)
        # end_note_idx = [-1] + [s['end_note'] for s in sections]
        for i, se in reversed(list(enumerate(sections))):
            # carry the 'end_note' to the next start
            se['end_note'] = start_note_idx[i + 1] - 1
            end_note_idx = [-1] + [s['end_note'] for s in sections]
            if se['slug'] == u'VOCAL_SECTION':
                # estimate the start of the lyrics sections
                next_lyrics_start_ind = self._find_vocal_section_start_idx(
                    se, score, start_note_idx, end_note_idx, measure_start_idx,
                    real_lyrics_idx)
                se['start_note'] = next_lyrics_start_ind

                # update start_note_idx
                start_note_idx = SectionExtractor._section_start_note_idx(
                    score, sections)

                # update lyrics
                section_lyrics_idx = ([rl for rl in real_lyrics_idx
                                       if se['start_note'] <= rl <=
                                       se['end_note']])

                syllables = [score['lyrics'][li] for li in section_lyrics_idx]
                se['lyrics'] = ''.join(syllables)
            else:  # instrumental
                pass  # the start and end are already fixed

        # if the first rows are control rows and the first section starts next
        if sections:
            first_note_idx = ScoreProcessor.get_first_note_index(score)

            first_sec = sections[0]
            # first_sec_idx = -1
            for ii, sec in enumerate(sections):
                if sec['start_note'] < first_sec['start_note']:
                    first_sec = sec
                    # first_sec_idx = ii

            # if there is a gap in the start, create a new section
            if first_sec['start_note'] > first_note_idx:
                sections.append({'name': u'INSTRUMENTAL_SECTION',
                                 'slug': u'INSTRUMENTAL_SECTION',
                                 'start_note': first_note_idx,
                                 'end_note': min([s['start_note']
                                                  for s in sections]) - 1})
        return self._sort_sections(sections)

    def _find_vocal_section_start_idx(self, section, score, start_note_idx,
                                      end_note_idx, measure_start_idx,
                                      real_lyrics_idx):

        first_note_idx = ScoreProcessor.get_first_note_index(score)
        prev_closest_start_ind = self.find_prev_closest_bound(
            start_note_idx, section['end_note'])
        prev_closest_end_ind = self.find_prev_closest_bound(
            end_note_idx, section['end_note'])

        # find where the lyrics of this section starts
        chk_ind = max([prev_closest_end_ind, prev_closest_start_ind])
        next_lyrics_start_ind = min(x for x in real_lyrics_idx if x > chk_ind)
        next_lyrics_measure_offset = floor(
            score['offset'][next_lyrics_start_ind])

        # check if next_lyrics_start_ind and prev_closest_end_ind are
        # in the same measure. Ideally they should be in different
        # measures
        if next_lyrics_measure_offset == floor(
                score['offset'][prev_closest_end_ind]):
            if self.print_warnings:
                warnings.warn(u'{0!s}: {1!s} and {2!s} are in the same '
                              u'measure!'.
                              format(str(next_lyrics_measure_offset),
                                     score['lyrics'][prev_closest_end_ind],
                                     score['lyrics'][next_lyrics_start_ind]))
            return next_lyrics_measure_offset
        else:  # The section starts on the first measure the lyrics
            # start
            return max([OffsetProcessor.get_measure_offset_id(
                next_lyrics_measure_offset, score['offset'],
                measure_start_idx), first_note_idx])

    @staticmethod
    def find_prev_closest_bound(bound_note_idx, end_note):
        try:  # find the previous closest end
            prev_closest_ind = max(x for x in bound_note_idx if x < end_note)
        except ValueError:  # no vocal sections
            prev_closest_ind = -1

        return prev_closest_ind

    @staticmethod
    def _section_start_note_idx(score, sections):
        # dummy add the last note + 1
        return [s['start_note'] for s in sections] + [len(score['lyrics'])]

    @staticmethod
    def _sort_sections(sections):
        # sort the sections
        sort_idx = [i[0] for i in sorted(enumerate([s['start_note']
                                                    for s in sections]),
                                         key=lambda x: x[1])]

        return [sections[s] for s in sort_idx]

    def _validate_sections(self, sections, score, ignore_labels, symbtrname):
        # treat some of these are warning; they'll be made stricter later
        if not sections:  # check section presence
            if self.print_warnings:
                warnings.warn(u"{0!s}, Missing section info in lyrics.".format(
                    symbtrname))
            valid_bool = True  # nothing to validate
        else:  # check section continuity
            section_continuity_bool = self._validate_section_continuity(
                score, sections, symbtrname)

            self._chk_measure_starts(ignore_labels, sections, score,
                                     symbtrname)

            section_bound_bool = self._validate_section_start_end(
                sections, score, symbtrname)

            # check if there are any structure labels with a space
            no_space_bool = self._validate_section_labels(score, symbtrname)

            valid_bool = all([section_continuity_bool, no_space_bool,
                              section_bound_bool])

        return valid_bool

    @staticmethod
    def _validate_section_start_end(sections, score, symbtrname):
        # check if the end of a section somehow got earlier than its start
        section_bound_bool = True
        for s in sections:
            if s['start_note'] > s['end_note']:
                warnstr = u'{0!s}, {1!s} -> {2!s}, {3!s} ends before it ' \
                          u'starts: {4!s}' \
                          u''.format(symbtrname, str(s['start_note']),
                                     str(s['end_note']), s['slug'],
                                     str(score['offset'][s['start_note']]))
                warnings.warn(warnstr)
                section_bound_bool = False

        return section_bound_bool

    def _chk_measure_starts(self, ignore_labels, sections, score, symbtrname):
        # check whether section starts on the measure or not
        for s in sections:
            starts_on_measure = not OffsetProcessor.is_integer_offset(
                score['offset'][s['start_note']]) and (s['slug'] not in
                                                       ignore_labels)
            if starts_on_measure and self.print_warnings:
                # This is not a warning but a indication to the user as it can
                # happen occasionally especially in the folk forms
                print(symbtrname + ", " + str(s['start_note']) +
                      ', ' + s['slug'] + ' does not start on a measure: ' +
                      str(score['offset'][s['start_note']]))

    @staticmethod
    def _validate_section_labels(score, symbtrname):
        all_labels = ScoreProcessor.get_all_symbtr_labels() + ['.']
        no_space_bool = False
        for i, ll in enumerate(score['lyrics']):
            for label in all_labels:
                # invalid lyrics end
                if label + ' ' in ll:
                    warnings.warn(u'{0!s}, {1!s}: Extra space in {2!s}'.format(
                        symbtrname, str(i), ll))
                    no_space_bool = False

        return no_space_bool

    def _validate_section_continuity(self, score, sections, symbtrname):
        first_note_idx = ScoreProcessor.get_first_note_index(score)
        ends = [first_note_idx - 1] + [s['end_note'] for s in sections]
        start_note_idx = self._section_start_note_idx(score, sections)

        section_continuity_bool = True
        for s, e in zip(start_note_idx, ends):
            if not s - e == 1:
                if self.print_warnings:
                    warnings.warn(u'{0!s}, {1!s} -> {2!s}, Gap between the '
                                  u'sections'.format(symbtrname,
                                                     str(e), str(s)))
                section_continuity_bool = False

        return section_continuity_bool
