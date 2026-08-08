from django import template

register = template.Library()


@register.filter
def query_value(querydict, key):
    return querydict.get(key, "")
