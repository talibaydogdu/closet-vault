from django.db.models import Q

FILTER_FIELDS = {
    "person": "person_id",
    "category": "category_id",
    "color": "primary_color__iexact",
    "secondary_color": "secondary_color__iexact",
    "brand": "brand__iexact",
    "size": "size__iexact",
    "waist_size": "waist_size__iexact",
    "inseam_size": "inseam_size__iexact",
    "shoe_size": "shoe_size__iexact",
    "material": "material__iexact",
    "pattern": "pattern__iexact",
    "fit": "fit__iexact",
    "season": "season__iexact",
    "status": "status",
    "tag": "tags__id",
    "storage_unit": "storage_unit_id",
    "unit_type": "storage_unit__unit_type",
}


def filter_items(queryset, params):
    for key, lookup in FILTER_FIELDS.items():
        if value := params.get(key):
            queryset = queryset.filter(**{lookup: value})
    if category := params.get("subcategory"):
        queryset = queryset.filter(category_id=category)
    if query := params.get("q"):
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(brand__icontains=query)
            | Q(model__icontains=query)
            | Q(notes__icontains=query)
            | Q(storage_unit__name__icontains=query)
            | Q(storage_unit__location_text__icontains=query)
        )
    return queryset.distinct()
