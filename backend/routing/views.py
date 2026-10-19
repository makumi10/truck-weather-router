import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .errors import PlanningError
from .planner import plan_trip
from .serializers import PlanRequestSerializer

log = logging.getLogger(__name__)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def plan(request):
    ser = PlanRequestSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"error": "Invalid input", "details": ser.errors}, status=400)
    v = ser.validated_data
    try:
        result = plan_trip(v["origin"], v["destination"], v["departure"], v["load_weight_lb"],
                           v["checkpoint_spacing"])
    except PlanningError as exc:
        return Response({"error": exc.message}, status=exc.status)
    except Exception:  # pragma: no cover - last-resort guard
        log.exception("Unexpected planning failure")
        return Response({"error": "Unexpected error while planning the trip."}, status=500)
    return Response(result)
