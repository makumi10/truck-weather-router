from rest_framework import serializers


class PlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure = serializers.DateTimeField()  # ISO 8601; naive values are treated as UTC
    load_weight_lb = serializers.IntegerField(min_value=0, max_value=200_000)
    checkpoint_spacing = serializers.ChoiceField(choices=["auto", "10", "25", "50"], default="auto")
