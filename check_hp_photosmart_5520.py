#!/bin/python3

import requests
import xml.etree.ElementTree as et
import re

# constants
__NAMESPACE_PUDYN = 'pudyn'
__NAMESPACE_DD    = 'dd'
__NAMESPACE_DD2   = 'dd2'

result  = requests.get('https://192.168.1.13/DevMgmt/ProductUsageDyn.xml', verify=False)
content = result.content.decode('utf-8')
xml     = et.fromstring(content)


# XML pre-processing
def _get_namespaces(xml_string):
    ns = {}
    for match in re.findall(r'xmlns:(\w+)\s*=\s*"(.*?)"', xml_string):
        ns[match[0]] = match[1]
    return ns


# XML children callbacks
def _callback_color(xml_node, namespaces={}):
    class Consumable:
        def __init__(self, name: str, remaining: int):
            self.name      = name
            self.remaining = remaining

    name  = XmlSearcher('MarkerColor'                          , __NAMESPACE_DD, callback=lambda x, y: x.text).search(xml_node, namespaces)[0]
    color = XmlSearcher('ConsumableRawPercentageLevelRemaining', __NAMESPACE_DD, callback=lambda x, y: x.text).search(xml_node, namespaces)[0]

    return Consumable(name, color)


class XmlSearcher:
    def __init__(self, tag_name, namespace=None, children=None, callback=None):
        self.__tag_name  = tag_name
        self.__namespace = namespace
        self.__children  = [] if children is None else [child for child in children if isinstance(child, XmlSearcher)]
        self.__callback  = callback

    def search(self, xml_node, namespaces={}):
        namespace = '' if self.__namespace is None else f'{self.__namespace}:'

        class Result(object):
            pass
        result = Result()
        setattr(result, self.__tag_name)

        for element in xml_node.findall(f'{namespace}{self.__tag_name}', namespaces):
            if self.__callback:
                append(self.__callback(element, namespaces))
            else:
                results = []
                for child in self.__children:
                    results.append(child.search(element, namespaces))
        return results


# Search groups (namespace, tag-name, children-tag-name, callback)
searcher = XmlSearcher('ConsumableSubunit', namespace=__NAMESPACE_PUDYN, children=(
        XmlSearcher('Consumable', namespace=__NAMESPACE_PUDYN, callback=_callback_color),
    ),
)

objects = searcher.search(xml, _get_namespaces(content))
objects = None
