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


class CheckStatus(Enum):
    OK       = 0
    WARNING  = 1
    CRITICAL = 2
    UNKNOWN  = 3


_check_status   = CheckStatus.UNKNOWN.value
_xml            = None
_xml_namespaces = {}


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


class FillLevelCheck:
    def __init__(self, color_name: str, percentage_warning: int, percentage_critial: int):
        self.color_name          = color_name
        self.percentage_warning  = percentage_warning
        self.percentage_critical = percentage_critial


class FillLevelCheckDispatcher:
    def __init__(self):
        self._checks = []

    def add(self, color_name: str, percentage_warning: int, percentage_critial: int):
        self._checks.append(FillLevelCheck(color_name, percentage_warning, percentage_critial))

    def perform_check(self):
        global _xml
        global _xml_namespaces

        _CONSUMABLE_SUBUNIT = 'ConsumableSubunit'
        _CONSUMABLE         = 'Consumable'

        check_status = CheckStatus.UNKNOWN
        searcher     = XmlSearcher(_CONSUMABLE_SUBUNIT, namespace=_PRINTER_XML_NAMESPACE_PUDYN, children=(
                XmlSearcher(_CONSUMABLE, namespace=_PRINTER_XML_NAMESPACE_PUDYN, callback=_callback_consumable),
            ),
        )
        results     = searcher.search(_xml, _xml_namespaces)
        color_infos = getattr(getattr(results, _CONSUMABLE_SUBUNIT), _CONSUMABLE)

        def has_highest_prio(compare_value: CheckStatus):
            return (check_status == CheckStatus.UNKNOWN or check_status.value <= compare_value.value)

        for check in self._checks:
            check_color_name = check.color_name.strip().lower()
            if isinstance(check, FillLevelCheck):
                for color_info in color_infos:
                    if color_info.name.lower().strip() == check_color_name:
                        if color_info.remaining <= check.percentage_critical:
                            check_status = CheckStatus.CRITICAL
                        elif color_info.remaining <= check.percentage_warning and has_highest_prio(CheckStatus.CRITICAL):
                            check_status = CheckStatus.WARNING
                        elif has_highest_prio(CheckStatus.WARNING):
                            check_status = CheckStatus.OK
                        break

        return check_status

# XML pre-processing
def _get_namespaces(xml_string):
    ns = {}
    for match in re.findall(r'xmlns:(\w+)\s*=\s*"(.*?)"', xml_string):
        ns[match[0]] = match[1]
    return ns


def _verify_host(hostname: str):
    return re.match(r'(^(www\.)?[a-zA-Z0-9]+\.[a-zA-Z]+$)|(^[0-9]+(\.[0-9]+){3}$)', hostname)


def _exit(check_status: CheckStatus, description: str=None):
    global _check_status

    if check_status == CheckStatus.OK:
        status = 'OK'
    elif check_status == CheckStatus.WARNING:
        status = 'WARNING'
    elif check_status == CheckStatus.CRITICAL:
        status = 'CRITICAL'
    else:
        status = 'UNKNOWN'

    print(f'{status}' + (f'|{description}' if description is not None else ''))
    exit(check_status.value)


def main():
    global _xml
    global _xml_namespaces

    parser = argparse.ArgumentParser()
    parser.add_argument('--hostname'  , required=True, type=str, help='Full qualified name or IP-address of printer'                                                                      )
    parser.add_argument('--fill-level', required=True, type=str, help='Color-fill-level to check (color-name warning-percentage-level critical-percentage-level', action='append', nargs=3)

    args = parser.parse_args()

    if not _verify_host(args.hostname):
        _exit(CheckStatus.UNKNOWN, 'Invalid Hostname')

    result  = requests.get(f'http://{args.hostname}/DevMgmt/ProductUsageDyn.xml', verify=False)
    content = result.content.decode('utf-8')

    # initialize global variables
    _xml            = ET.fromstring(content)
    _xml_namespaces = _get_namespaces(content)

    try:
        # process color checks
        if args.fill_level:
            filllevel_check_dispatcher = FillLevelCheckDispatcher()

            for fill_level in args.fill_level:
                filllevel_check_dispatcher.add(fill_level[0], int(fill_level[1]), int(fill_level[2]))
            color_check_result = filllevel_check_dispatcher.perform_check()
            _exit(color_check_result)

        _exit(CheckStatus.UNKNOWN, 'Unknown color requested')
    except AttributeError as e:
        _exit(CheckStatus.UNKNOWN, 'Unknown attribute requested')
    except Exception as e:
        _exit(CheckStatus.UNKNOWN, 'An unexpected error has occurred')


if __name__ == '__main__':
    main()
