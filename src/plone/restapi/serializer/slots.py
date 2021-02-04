from plone.restapi.interfaces import IBlockFieldSerializationTransformer
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.interfaces import ISlot
from plone.restapi.interfaces import ISlots
from plone.restapi.serializer.converters import json_compatible
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.component import subscribers
from zope.interface import implementer
from zope.interface import Interface

import copy


SERVICE_ID = "@slots"


@adapter(Interface, ISlot, Interface)
@implementer(ISerializeToJson)
class SlotSerializer(object):
    """Default serializer for a single persistent slot"""

    def __init__(self, context, slot, request):
        self.context = context
        self.request = request
        self.slot = slot

    def __call__(self, name):
        slot_blocks = copy.deepcopy(self.slot_blocks)
        slot_blocks_layout = copy.deepcopy(self.slot_blocks_layout)

        for id, block_value in slot_blocks.items():
            block_type = block_value.get("@type", "")
            handlers = []
            for h in subscribers(
                (self.context, self.request), IBlockFieldSerializationTransformer
            ):
                if h.block_type == block_type or h.block_type is None:
                    handlers.append(h)

            for handler in sorted(handlers, key=lambda h: h.order):
                if not getattr(handler, "disabled", False):
                    block_value = handler(block_value)

            slot_blocks[id] = json_compatible(block_value)

        return {
            "@id": "{0}/{1}/{2}".format(self.context.absolute_url, SERVICE_ID, name),
            "slot_blocks": slot_blocks,
            "slot_blocks_layout": slot_blocks_layout,
        }


@adapter(Interface, ISlots, Interface)
@implementer(ISerializeToJson)
class SlotsSerializer(object):
    """Default slots storage serializer"""

    def __call__(self):
        result = []
        storage = ISlots(self.context)

        for name, slot in storage.items():
            serializer = getMultiAdapter(
                (self.context, slot, self.request), ISerializeToJson
            )
            result.append(serializer(name))

        return result
