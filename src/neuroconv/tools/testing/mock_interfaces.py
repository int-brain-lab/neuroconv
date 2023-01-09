"""Authors: Cody Baker."""
from typing import Optional, List

import numpy as np

from .mock_ttl_signals import generate_mock_ttl_signal
from ...datainterfaces import SpikeGLXNIDQInterface


class MockSpikeGLXNIDQInterface(SpikeGLXNIDQInterface):
    ExtractorName = "NumpyRecording"

    def __init__(
        self, signal_duration: float = 7.0, ttl_times: Optional[List[List[float]]] = None, ttl_duration: float = 1.0
    ):
        """
        Define a mock SpikeGLXNIDQInterface by overriding the recording extractor to be a mock TTL signal.

        # TODO, allow definition of channel names and more than one TTL, if desired.
        # TODO, make the metadata of this mock mimic the true thing

        Parameters
        ----------
        signal_duration : float, default: 7.0
            The number of seconds to simulate.
        ttl_times : list of list of floats, optional
            The times within the `signal_duration` to trigger the TTL pulse for each channel.
            The outer list is over channels, while each inner list is the set of TTL times for each specific channel.
            The default generates 8 channels with periodic on/off cycle (which start in the 'off' state)
            each of which is of length `ttl_duration` with a 0.1 second offset per channel.
        ttl_duration : float, default: 1.0
            How long the TTL pulses stays in the 'on' state when triggered, in seconds.
        """
        from spikeinterface.extractors import NumpyRecording

        if ttl_times is None:
            # Begin in 'off' state
            number_of_periods = int(np.ceil((signal_duration - ttl_duration) / (ttl_duration * 2)))
            default_periodic_ttl_times = [ttl_duration * (1 + 2 * period) for period in range(number_of_periods)]
            ttl_times = [[ttl_time + 0.1 * channel for ttl_time in default_periodic_ttl_times] for channel in range(8)]
        number_of_channels = len(ttl_times)
        channel_ids = [f"nidq#XA{channel_index}" for channel_index in range(number_of_channels)]  # NIDQ channel IDs

        sampling_frequency = 25_000.0  # NIDQ sampling rate
        number_of_frames = int(signal_duration * sampling_frequency)
        traces = np.empty(shape=(number_of_frames, number_of_channels), dtype="int16")
        for channel_index in range(number_of_channels):
            traces[:, channel_index] = generate_mock_ttl_signal(
                signal_duration=signal_duration,
                ttl_times=ttl_times[channel_index],
                ttl_duration=ttl_duration,
                sampling_frequency_hz=sampling_frequency,
            )

        self.recording_extractor = NumpyRecording(
            traces_list=traces, sampling_frequency=sampling_frequency, channel_ids=channel_ids
        )
        # NIDQ channel gains
        self.recording_extractor.set_channel_gains(gains=[61.03515625] * self.recording_extractor.get_num_channels())

        # Minimal meta so `get_metadata` works similarly to real NIDQ header
        self.meta = {"acqMnMaXaDw": "0,0,8,1", "fileCreateTime": "2020-11-03T10:35:10", "niDev1ProductName": "PCI-6259"}
