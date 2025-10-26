from rest_framework import serializers

class AutoRefNameSerializer(serializers.ModelSerializer):
    """Automatically assign unique ref_name for drf_yasg"""
    class Meta:
        ref_name = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, 'Meta'):
            if getattr(cls.Meta, 'ref_name', None) is None:
                cls.Meta.ref_name = f"{cls.__module__.replace('.', '_')}_{cls.__name__}"
