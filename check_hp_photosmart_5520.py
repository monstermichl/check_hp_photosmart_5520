#!/bin/python3

import requests
import xml.etree.ElementTree as ET
import re
import argparse

from enum import Enum

# constants
__PRINTER_XML_NAMESPACE_PUDYN = 'pudyn'
__PRINTER_XML_NAMESPACE_DD    = 'dd'
__PRINTER_XML_NAMESPACE_DD2   = 'dd2'


class ExitCode(Enum):
    OK       = 0
    WARNING  = 1
    CRITICAL = 2
    UNKNOWN  = 3


__exit_code = ExitCode.UNKNOWN.value


# XML children callbacks
def _callback_consumable(xml_node, namespaces):
    class Consumable:
        def __init__(self, name: str, remaining: int):
            self.name      = name
            self.remaining = remaining

    name  = XmlSearcher('MarkerColor'                          , __PRINTER_XML_NAMESPACE_DD, callback=lambda x, y: x.text).search(xml_node, namespaces)
    color = XmlSearcher('ConsumableRawPercentageLevelRemaining', __PRINTER_XML_NAMESPACE_DD, callback=lambda x, y: x.text).search(xml_node, namespaces)

    return Consumable(name, color)


# XML magic
class XmlSearcher:
    def __init__(self, tag_name, namespace=None, children=None, callback=None):
        self.__tag_name  = tag_name
        self.__namespace = namespace
        self.__children  = [] if children is None else [child for child in children if isinstance(child, XmlSearcher)]
        self.__callback  = callback

    def search(self, xml_node, namespaces):
        namespace = '' if self.__namespace is None else f'{self.__namespace}:'
        results   = []

        class Result(object):
            pass
        temp_result = Result()

        for element in xml_node.findall(f'{namespace}{self.__tag_name}', namespaces):
            if self.__callback:
                results.append(self.__callback(element, namespaces))
            else:
                for child in self.__children:
                    results.append(child.search(element, namespaces))

        if len(results) == 1:
            results = results[0]
        setattr(temp_result, self.__tag_name, results)
        return temp_result


# Search groups (namespace, tag-name, children-tag-name, callback)
searcher = XmlSearcher('ConsumableSubunit', namespace=__PRINTER_XML_NAMESPACE_PUDYN, children=(
        XmlSearcher('Consumable', namespace=__PRINTER_XML_NAMESPACE_PUDYN, callback=_callback_consumable),
    ),
)


# XML pre-processing
def _get_namespaces(xml_string):
    ns = {}
    for match in re.findall(r'xmlns:(\w+)\s*=\s*"(.*?)"', xml_string):
        ns[match[0]] = match[1]
    return ns


def _verify_host(hostname: str):
    return re.match(r'(^((http(s)?:\/\/)?www\.)?[a-zA-Z0-9]+\.[a-zA-Z]+$)|(^[0-9]+(\.[0-9]+){3}$)', hostname)


def _echo_status_and_set_exit_code(exit_code: ExitCode, description: str):
    global __exit_code

    if exit_code == ExitCode.OK:
        status = 'OK'
    elif exit_code == ExitCode.WARNING:
        status = 'WARNING'
    elif exit_code == ExitCode.CRITICAL:
        status = 'CRITICAL'
    else:
        status = 'UNKNOWN'

    print(status + f'{status}|{description}')
    __exit_code = exit_code.value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hostname', required=True, type=str, help='Full qualified name or IP-address of printer'           )
    parser.add_argument('--color'   , required=True, type=str, help='Color to check'                                         )
    parser.add_argument('--warning' , required=True, type=int, help='Percentage level at which a warning is triggered'       )
    parser.add_argument('--critical', required=True, type=int, help='Percentage level at which a critical error is triggered')

    args = parser.parse_args()

    if not _verify_host(args.hostname):
        _echo_status_and_set_exit_code(ExitCode.UNKNOWN, 'Invalid Hostname')
    else:
        result  = requests.get(f'{args.hostname}/DevMgmt/ProductUsageDyn.xml', verify=False)
        content = result.content.decode('utf-8')
        xml     = ET.fromstring(content)

        objects = searcher.search(xml, _get_namespaces(content))
        objects = None


if __name__ == '__main__':
    main()
    exit(__exit_code)

