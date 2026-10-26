"""An array as an HTTP body in NPY format, the self-describing header the data has on disk."""

from __future__ import annotations

import io

import numpy as np
from fastapi.responses import Response

MEDIA_TYPE = "application/x-npy"


def npy_response(array: np.ndarray) -> Response:
    buffer = io.BytesIO()
    np.save(buffer, np.ascontiguousarray(array), allow_pickle=False)
    return Response(
        content=buffer.getvalue(),
        media_type=MEDIA_TYPE,
        headers={
            "X-Shape": ",".join(str(side) for side in array.shape),
            "X-Dtype": str(array.dtype),
        },
    )
