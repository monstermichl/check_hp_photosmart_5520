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
    def __init__(self, color_name: str, percentage_warning: int, percentage_critial: int, percentage_actual: int=0, status: CheckStatus=None):
        self.color_name          = color_name
        self.percentage_warning  = percentage_warning
        self.percentage_critical = percentage_critial
        self.percentage_actual   = percentage_actual
        self.status              = status

    def __str__(self):
        return f'{self.color_name} {self.percentage_actual}%'


class FillLevelCheckDispatcher:
    def __init__(self):
        self.checks = []

    def add(self, color_name: str, percentage_warning: int, percentage_critial: int):
        self.checks.append(FillLevelCheck(color_name, percentage_warning, percentage_critial))

    def perform_check(self):
        global _xml
        global _xml_namespaces

        _CONSUMABLE_SUBUNIT = 'ConsumableSubunit'
        _CONSUMABLE         = 'Consumable'

        fill_level_check = None
        searcher         = XmlSearcher(_CONSUMABLE_SUBUNIT, namespace=_PRINTER_XML_NAMESPACE_PUDYN, children=(
                XmlSearcher(_CONSUMABLE, namespace=_PRINTER_XML_NAMESPACE_PUDYN, callback=_callback_filllevel),
            ),
        )
        results     = searcher.search(_xml, _xml_namespaces)
        color_infos = getattr(getattr(results, _CONSUMABLE_SUBUNIT), _CONSUMABLE)

        def has_highest_prio(compare_value: CheckStatus):
            return (fill_level_check is None or fill_level_check.status == CheckStatus.UNKNOWN or fill_level_check.status.value <= compare_value.value)

        for check in self.checks:
            check_color_name = check.color_name.strip().lower()
            if isinstance(check, FillLevelCheck):
                for color_info in color_infos:
                    if color_info.name.lower().strip() == check_color_name:
                        copy = False

                        # perform status evaluation
                        if color_info.remaining <= check.percentage_critical:
                            temp_check_status = CheckStatus.CRITICAL
                            copy              = True
                        elif color_info.remaining <= check.percentage_warning:
                            temp_check_status = CheckStatus.WARNING
                            if has_highest_prio(CheckStatus.CRITICAL):
                                copy = True
                        else:
                            temp_check_status = CheckStatus.OK
                            if has_highest_prio(CheckStatus.WARNING):
                                copy = True

                        # assign individual status
                        check.percentage_actual = color_info.remaining
                        check.status            = temp_check_status

                        # if copy is true, the currently processed color has the highest status
                        if copy:
                            fill_level_check = check
                        break

        return fill_level_check


class ArgumentSplitException(Exception):
    def __init__(self, array_length: int, number_arguments: int):
        super().__init__(f'Array length is {array_length} but must be a multiple of {number_arguments} to be splitted')


# XML pre-processing
def _get_namespaces(xml_string):
    ns = {}
    for match in re.findall(r'xmlns:(\w+)\s*=\s*"(.*?)"', xml_string):
        ns[match[0]] = match[1]
    return ns


# callbacks
def _callback_filllevel(xml_node, namespaces):
    _XML_KEY_COLOR     = 'MarkerColor'
    _XML_KEY_REMAINING = 'ConsumableRawPercentageLevelRemaining'

    class Consumable:
        def __init__(self, name: str, remaining: int):
            self.name      = name
            self.remaining = remaining

    name      = str(getattr(XmlSearcher(_XML_KEY_COLOR    , _PRINTER_XML_NAMESPACE_DD, callback=lambda x, y: x.text).search(xml_node, namespaces), _XML_KEY_COLOR    ))
    remaining = int(getattr(XmlSearcher(_XML_KEY_REMAINING, _PRINTER_XML_NAMESPACE_DD, callback=lambda x, y: x.text).search(xml_node, namespaces), _XML_KEY_REMAINING))

    return Consumable(name, remaining)


def _verify_host(hostname: str):
    return re.match(r'(^(www\.)?[a-zA-Z0-9]+\.[a-zA-Z]+$)|(^[0-9]+(\.[0-9]+){3}$)', hostname)


def _split_multiple_args(array: list, number_arguments: int):
    splitted_array = []
    length_array   = len(array)

    if length_array % number_arguments != 0:
        raise ArgumentSplitException(length_array, number_arguments)

    for i in range(0, len(array), number_arguments):
        splitted_array.append(array[i:i+number_arguments])
    return splitted_array


def _exit(check_status: CheckStatus, description: str=None, performance_data: str=None):
    global _check_status

    if check_status == CheckStatus.OK:
        status = 'OK'
    elif check_status == CheckStatus.WARNING:
        status = 'WARNING'
    elif check_status == CheckStatus.CRITICAL:
        status = 'CRITICAL'
    else:
        status = 'UNKNOWN'

    print(f'{status}' + (f' - {description}' if description is not None else '') + (f'|{performance_data}' if performance_data is not None else ''))
    exit(check_status.value)


def main():
    global _xml
    global _xml_namespaces

    parser = argparse.ArgumentParser()
    parser.add_argument('--hostname'  , required=True, type=str, help='Full qualified name or IP-address of printer'                                                                         )
    parser.add_argument('--fill-level', required=True, type=str, help='Color-fill-level to check (color-name warning-percentage-level critical-percentage-level)', action='append', nargs='+')

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
            _LENGTH_ARGUMENTS_FILL_LEVEL = 3

            # multiple colors can also be provided with one --fill-level parameter
            fill_level_length = len(args.fill_level)
            if fill_level_length == 1:
                args.fill_level = _split_multiple_args(args.fill_level[0], _LENGTH_ARGUMENTS_FILL_LEVEL)
            filllevel_check_dispatcher = FillLevelCheckDispatcher()

            for fill_level in args.fill_level:
                filllevel_check_dispatcher.add(fill_level[0], int(fill_level[1]), int(fill_level[2]))
            fill_level_check = filllevel_check_dispatcher.perform_check()
            _exit(fill_level_check.status, performance_data=', '.join([str(check) for check in filllevel_check_dispatcher.checks]))

        _exit(CheckStatus.UNKNOWN, description='Unknown color requested')
    except AttributeError as e:
        _exit(CheckStatus.UNKNOWN, description='Unknown attribute requested')
    except Exception as e:
        _exit(CheckStatus.UNKNOWN, description='An unexpected error has occurred')


if __name__ == '__main__':
    main()
