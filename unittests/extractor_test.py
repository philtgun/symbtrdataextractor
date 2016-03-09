from symbtrdataextractor.SymbTrDataExtractor import SymbTrDataExtractor
from symbtrdataextractor.SymbTrReader import SymbTrReader
import json
import os


def test_extractor():
    # inputs
    scorename = 'kurdilihicazkar--sarki--agiraksak--ehl-i_askin--tatyos_efendi'

    txt_filename = os.path.join('sampledata', scorename + '.txt')

    mbid = 'b43fd61e-522c-4af4-821d-db85722bf48c'

    auto_seg_file = os.path.join('sampledata', scorename + '.autoSeg')
    auto_seg_bounds = json.load(open(auto_seg_file, 'r'))['boundary_noteIdx']

    mu2_filename = os.path.join('sampledata', scorename + '.mu2')

    # initialize the extractor
    extractor = SymbTrDataExtractor(
        extract_all_labels=False, melody_sim_thres=0.75, lyrics_sim_thres=0.75,
        get_recording_rels=False, print_warnings=True)

    # extract txt_data
    txt_data, is_data_valid = extractor.extract(
        txt_filename, symbtr_name=scorename, mbid=mbid,
        segment_note_bound_idx=auto_seg_bounds)

    # extract mu2 header metadata
    mu2_header, header_row, is_header_valid = SymbTrReader.read_mu2_header(
        mu2_filename, symbtr_name=scorename)

    # merge
    data = SymbTrDataExtractor.merge(txt_data, mu2_header)

    # compare with a previously saved result
    score_data_file = os.path.join('unittests', scorename + '.json')
    saved_data = json.load(open(score_data_file))

    assert saved_data == data