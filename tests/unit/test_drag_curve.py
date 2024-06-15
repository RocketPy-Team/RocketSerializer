import os
from pathlib import Path

import pytest

from rocketserializer.components.drag_curve import save_drag_curve

# @pytest.mark.parametrize(
#     "datapoints, data_labels, output_folder",
#     [(), (), ()],
# )
# def test_save_drag_curve(datapoints, data_labels, output_folder):
#     res = save_drag_curve(datapoints, data_labels, output_folder)
#     os.remove(output_folder + "drag_curve.csv")
#     assert isinstance(res, (str, Path))
#     assert Path(res).exists()
