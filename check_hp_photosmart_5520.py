#!/bin/python3

import requests
import xml.etree.ElementTree as ET
import re
import argparse

from enum import Enum

# constants
_PRINTER_XML_NAMESPACE_PUDYN = 'pudyn'
_PRINTER_XML_NAMESPACE_DD    = 'dd'
_PRINTER_XML_NAMESPACE_DD2   = 'dd2'


class ExitCode(Enum):
    OK       = 0
    WARNING  = 1
    CRITICAL = 2
    UNKNOWN  = 3


__exit_code = ExitCode.UNKNOWN.value


# XML children callbacks
def _callback_consumable(xml_node, namespaces):
    _XML_KEY_COLOR     = 'MarkerColor'
    _XML_KEY_REMAINING = 'ConsumableRawPercentageLevelRemaining'

    class Consumable:
        def __init__(self, name: str, remaining: int):
            self.name      = name
            self.remaining = remaining

    name      = str(getattr(XmlSearcher(_XML_KEY_COLOR    , _PRINTER_XML_NAMESPACE_DD, callback=lambda x, y: x.text).search(xml_node, namespaces), _XML_KEY_COLOR    ))
    remaining = int(getattr(XmlSearcher(_XML_KEY_REMAINING, _PRINTER_XML_NAMESPACE_DD, callback=lambda x, y: x.text).search(xml_node, namespaces), _XML_KEY_REMAINING))

    return Consumable(name, remaining)


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


# XML pre-processing
def _get_namespaces(xml_string):
    ns = {}
    for match in re.findall(r'xmlns:(\w+)\s*=\s*"(.*?)"', xml_string):
        ns[match[0]] = match[1]
    return ns


def _verify_host(hostname: str):
    return re.match(r'(^(www\.)?[a-zA-Z0-9]+\.[a-zA-Z]+$)|(^[0-9]+(\.[0-9]+){3}$)', hostname)


def _exit(exit_code: ExitCode, description: str):
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
    exit(exit_code.value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hostname', required=True, type=str, help='Full qualified name or IP-address of printer'           )
    parser.add_argument('--color'   , required=True, type=str, help='Color to check'                                         )
    parser.add_argument('--warning' , required=True, type=int, help='Percentage level at which a warning is triggered'       )
    parser.add_argument('--critical', required=True, type=int, help='Percentage level at which a critical error is triggered')

    args = parser.parse_args()

    if not _verify_host(args.hostname):
        _exit(ExitCode.UNKNOWN, 'Invalid Hostname')

    result  = requests.get(f'https://{args.hostname}/DevMgmt/ProductUsageDyn.xml', verify=False)
    content = result.content.decode('utf-8')
    xml     = ET.fromstring(content)

    try:
        _CONSUMABLE_SUBUNIT = 'ConsumableSubunit'
        _CONSUMABLE         = 'Consumable'

        # Search groups (tag-name, namespace, children-tag-name, callback)
        searcher = XmlSearcher(_CONSUMABLE_SUBUNIT, namespace=_PRINTER_XML_NAMESPACE_PUDYN, children=(
                XmlSearcher(_CONSUMABLE, namespace=_PRINTER_XML_NAMESPACE_PUDYN, callback=_callback_consumable),
            ),
        )
        results       = searcher.search(xml, _get_namespaces(content))
        colors        = getattr(getattr(results, _CONSUMABLE_SUBUNIT), _CONSUMABLE)
        compare_color = args.color.lower().strip()

        for color in colors:
            if color.name.lower().strip() == compare_color:
                if color.remaining <= args.critical:
                    exit_code = ExitCode.CRITICAL
                elif color.remaining <= args.warning:
                    exit_code = ExitCode.CRITICAL
                else:
                    exit_code = ExitCode.OK
                _exit(exit_code, f'{color.remaining}% for {color.name}')
        _exit(ExitCode.UNKNOWN, 'Unknown color requested')

    except AttributeError as e:
        _exit(ExitCode.UNKNOWN, 'Unknown attribute requested')
    except Exception as e:
        _exit(ExitCode.UNKNOWN, 'An unexpected error has occurred')


if __name__ == '__main__':
    main()
