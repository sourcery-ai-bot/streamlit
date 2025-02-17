# Copyright 2018-2022 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import threading
from collections import deque
from enum import Enum
from typing import Any, Optional, Tuple, Deque, Iterable, Callable, TypeVar

import attr

from streamlit.proto.WidgetStates_pb2 import WidgetStates
from streamlit.state import coalesce_widget_states


class ScriptRequest(Enum):
    # Stop the script, but don't shutdown the ScriptRunner (data=None)
    STOP = "STOP"
    # Rerun the script (data=RerunData)
    RERUN = "RERUN"
    # Shut down the ScriptRunner, stopping any running script first (data=None)
    SHUTDOWN = "SHUTDOWN"


@attr.s(auto_attribs=True, slots=True, frozen=True)
class RerunData:
    """Data attached to RERUN requests. Immutable."""

    query_string: str = ""
    widget_states: Optional[WidgetStates] = None


class ScriptRequestQueue:
    """A thread-safe queue of ScriptRequests.

    AppSession publishes to this queue, and ScriptRunner consumes from it.

    """

    def __init__(self):
        self._lock = threading.Lock()
        self._queue: Deque[Tuple[ScriptRequest, Any]] = deque()

    @property
    def has_request(self) -> bool:
        """True if the queue has at least one element"""
        with self._lock:
            return len(self._queue) > 0

    def enqueue(self, request: ScriptRequest, data: Any = None) -> None:
        """Enqueue a new request to the end of the queue.

        This request may be coalesced with an existing request if appropriate.
        For example, multiple consecutive RERUN requests will be combined
        so that there's only ever one pending RERUN request in the queue
        at a time.

        Parameters
        ----------
        request : ScriptRequest
            The type of request

        data : Any
            Data associated with the request, if any. For example, could be of type RerunData.
        """

        with self._lock:
            if request == ScriptRequest.SHUTDOWN:
                # If we get a shutdown request, it jumps to the front of the
                # queue to be processed immediately.
                self._queue.appendleft((request, data))
                return

            if request == ScriptRequest.RERUN:
                # RERUN requests are special - if there's an existing rerun
                # request in the queue, we try to coalesce this one into it
                # to avoid having redundant RERUNS.
                index = _index_if(self._queue, lambda item: item[0] == request)
                if index >= 0:
                    _, old_data = self._queue[index]

                    if old_data.widget_states is None:
                        # The existing request's widget_states is None, which
                        # means it wants to rerun with whatever the most
                        # recent script execution's widget state was.
                        # We have no meaningful state to merge with, and
                        # so we simply overwrite the existing request.
                        self._queue[index] = (
                            request,
                            RerunData(
                                query_string=data.query_string,
                                widget_states=data.widget_states,
                            ),
                        )
                        return

                    if data.widget_states is not None:
                        # Both the existing and the new request have
                        # non-null widget_states. Merge them together.
                        coalesced_states = coalesce_widget_states(
                            old_data.widget_states, data.widget_states
                        )
                        self._queue[index] = (
                            request,
                            RerunData(
                                query_string=data.query_string,
                                widget_states=coalesced_states,
                            ),
                        )
                        return

                    # `old_data.widget_states is not None and data.widget_states is None` -
                    # this new request is entirely redundant and can be dropped.
                    return

            # Base case: add the request to the end of the queue.
            self._queue.append((request, data))

    def dequeue(self) -> Tuple[Optional[ScriptRequest], Any]:
        """Pops the front-most request from the queue and returns it.

        Returns (None, None) if the queue is empty.

        Returns
        -------
        A (ScriptRequest, Data) tuple.
        """
        with self._lock:
            return self._queue.popleft() if len(self._queue) > 0 else (None, None)


T = TypeVar("T")


def _index_if(collection: Iterable[T], pred: Callable[[T], bool]) -> int:
    """Find the index of the first item in a collection for which a predicate is true.

    Returns the index, or -1 if no such item exists.
    """
    return next(
        (index for index, element in enumerate(collection) if pred(element)),
        -1,
    )
