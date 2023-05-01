from plone import api
from plone.dexterity.interfaces import IDexterityContent
from plone.restapi.interfaces import IFieldSerializer
from plone.restapi.interfaces import IJsonCompatible
from plone.restapi.interfaces import ISerializeToJsonSummary
from plone.restapi.serializer.converters import json_compatible
from plone.restapi.serializer.dxfields import DefaultFieldSerializer
from z3c.relationfield.interfaces import IRelationChoice
from z3c.relationfield.interfaces import IRelationList
from z3c.relationfield.interfaces import IRelationValue
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.globalrequest import getRequest
from zope.interface import implementer
from zope.interface import Interface


@adapter(IRelationValue)
@implementer(IJsonCompatible)
def relationvalue_converter(value):
    mtool = api.portal.get_tool("portal_membership")
    if value.to_object and mtool.checkPermission("View", value.to_object):
        request = getRequest()
        request.form["metadata_fields"] = ["UID"]
        summary = getMultiAdapter((value.to_object, request), ISerializeToJsonSummary)()
        return json_compatible(summary)


@adapter(IRelationChoice, IDexterityContent, Interface)
@implementer(IFieldSerializer)
class RelationChoiceFieldSerializer(DefaultFieldSerializer):
    pass


@adapter(IRelationList, IDexterityContent, Interface)
@implementer(IFieldSerializer)
class RelationListFieldSerializer(DefaultFieldSerializer):
    def __call__(self):
        value = self.get_value()
        if value:
            return [item for item in json_compatible(value) if item]
        else:
            return super().__call__()
