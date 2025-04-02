from typing import List, Optional

from misc.PreprocessingFramework.DataProcessor import check_data_dimensions, T_Data, T_Timestamps
from misc.PreprocessingFramework.ProcessingNode import ProcessingNode

import logging

logger = logging.getLogger(__name__)

class ChannelSelectorNode(ProcessingNode):
    def __init__(self, in_channel_labels: List[str], selected_channels: Optional[List[str]] = None, excluded_channels: Optional[List[str]] = None, rename_channels: Optional[dict] = None, **settings):
        super().__init__(in_channel_labels, **settings)

        # Do not exclude channels if not supposed to
        if excluded_channels is None:
            excluded_channels = []

        # Select all channels if no selection is given. But exclude the excluded ones
        if selected_channels is None:
            selected_channels = [label for label in self.in_channel_labels if label not in excluded_channels]

        selected_but_not_in_channel = [label for label in selected_channels if label not in self.in_channel_labels]
        if selected_but_not_in_channel:
            logger.warning(f"{len(selected_but_not_in_channel)} channel(s) are in selected channels but not provided in in_channel_labels: {selected_but_not_in_channel}")


        if rename_channels is None:
            rename_channels = dict()

        self.selected_channels = []
        self.selected_channels_indices = []

        out_channel_labels = []
        for label in self.in_channel_labels:
            if label in selected_channels:
                if label in excluded_channels:
                    logger.warning(f"Channel {label} is in selected AND excluded channel labels. Defaulting to include")
                self.selected_channels.append(label)
                self.selected_channels_indices.append(self.in_channel_labels.index(label))
                out_channel_labels.append(rename_channels.get(label, label))  # Get the renamed label. If none given default to label

        self.out_channel_labels = out_channel_labels

    @check_data_dimensions
    def process(self, data: T_Data, timestamps: T_Timestamps=None, *args: any, **kwargs: any) -> (T_Data, T_Timestamps):
        if data is None:
            return None, timestamps
        data_reordered = data[:, self.selected_channels_indices, ...]
        return data_reordered, timestamps

    def get_settings(self, *args, **kwargs):
        settings = super().get_settings(*args, **kwargs)
        settings['selected_channels'] = self.selected_channels
        settings['_selected_channels_indices'] = self.selected_channels_indices
        return settings