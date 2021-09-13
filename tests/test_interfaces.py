from jsonschema import Draft7Validator
import numpy as np
from tempfile import mkdtemp
from shutil import rmtree
from pathlib import Path
from itertools import product

import pytest
import spikeextractors as se

try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False

from nwb_conversion_tools import (
    NWBConverter, MovieInterface, SIPickleRecordingExtractorInterface, SIPickleSortingExtractorInterface, interface_list
)


@pytest.mark.parametrize("data_interface", interface_list)
def test_interface_source_schema(data_interface):
    schema = data_interface.get_source_schema()
    Draft7Validator.check_schema(schema)


@pytest.mark.parametrize("data_interface", interface_list)
def test_interface_conversion_options_schema(data_interface):
    schema = data_interface.get_conversion_options_schema()
    Draft7Validator.check_schema(schema)


def test_pkl_interface():
    toy_data = se.example_datasets.toy_example()
    test_dir = Path(mkdtemp())
    output_folder = test_dir / "test_pkl"
    nwbfile_path = str(test_dir / "test_pkl_files.nwb")

    se.save_si_object(object_name="test_recording", si_object=toy_data[0], output_folder=output_folder)
    se.save_si_object(object_name="test_sorting", si_object=toy_data[1], output_folder=output_folder)
    print([x for x in output_folder.iterdir()])

    class SpikeInterfaceTestNWBConverter(NWBConverter):
        data_interface_classes = dict(
            Recording=SIPickleRecordingExtractorInterface, Sorting=SIPickleRecordingExtractorInterface
        )
    source_data = dict(
        Recording=dict(pkl_file=str(test_dir / "test_pkl" / "test_recording.pkl")),
        Sorting=dict(pkl_file=str(test_dir / "test_pkl" / "test_sorting.pkl"))
    )
    converter = SpikeInterfaceTestNWBConverter(source_data=source_data)
    converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    nwb_recording = se.NwbRecordingExtractor(file_path=nwbfile_path)
    nwb_sorting = se.NwbSortingExtractor(file_path=nwbfile_path)
    se.testing.check_recordings_equal(RX1=toy_data[0], RX2=nwb_recording)
    se.testing.check_recordings_equal(RX1=toy_data[0], RX2=nwb_recording, return_scaled=False)
    se.testing.check_sortings_equal(SX1=toy_data[1], SX2=nwb_sorting)


def test_movie_interface():
    if HAVE_OPENCV:
        test_dir = Path(mkdtemp())
        movie_file = test_dir / "test1.avi"
        nwbfile_path = str(test_dir / "test1.nwb")
        (nf, nx, ny) = (50, 640, 480)
        writer = cv2.VideoWriter(
            filename=str(movie_file),
            apiPreference=None,
            fourcc=cv2.VideoWriter_fourcc("M", "J", "P", "G"),
            fps=25,
            frameSize=(ny, nx),
            params=None,
        )
        for k in range(nf):
            writer.write(np.random.randint(0, 255, (nx, ny, 3)).astype("uint8"))
        writer.release()

        class MovieTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Movie=MovieInterface)

        source_data = dict(Movie=dict(file_paths=[movie_file]))
        converter = MovieTestNWBConverter(source_data)
        metadata = converter.get_metadata()

        # Default usage
        converter.run_conversion(metadata=metadata, nwbfile_path=nwbfile_path, overwrite=True)

        # This conversion option operates independently of all others
        converter.run_conversion(
            metadata=metadata,
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=dict(Movie=dict(starting_times=[123.0])),
        )

        # These conversion options do not operate independently, so test them jointly
        conversion_options_testing_matrix = [
            dict(Movie=dict(external_mode=False, stub_test=x, chunk_data=y))
            for x, y in product([True, False], repeat=2)
        ]
        for conversion_options in conversion_options_testing_matrix:
            converter.run_conversion(
                metadata=metadata, nwbfile_path=nwbfile_path, overwrite=True, conversion_options=conversion_options
            )

        module_name = "TestModule"
        module_description = "This is a test module."
        nwbfile = converter.run_conversion(metadata=metadata, save_to_file=False)
        assert f"Video: {Path(movie_file).stem}" in nwbfile.acquisition
        nwbfile = converter.run_conversion(
            metadata=metadata,
            save_to_file=False,
            nwbfile=nwbfile,
            conversion_options=dict(Movie=dict(module_name=module_name)),
        )
        assert module_name in nwbfile.modules
        nwbfile = converter.run_conversion(
            metadata=metadata,
            save_to_file=False,
            conversion_options=dict(Movie=dict(module_name=module_name, module_description=module_description)),
        )
        assert module_name in nwbfile.modules and nwbfile.modules[module_name].description == module_description
        rmtree(test_dir)
