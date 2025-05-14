from django import template

register = template.Library()

@register.filter
def modulo(value, arg):
    return value % arg

@register.filter
def get_range(start, end):
    return range(start, end)
