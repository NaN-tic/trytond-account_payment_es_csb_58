## coding: utf-8
# This file is part of account_payment_es_csb_58 module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
import logging

try:
    from retrofix import Record, write, c58
except ImportError:
    logger = logging.getLogger(__name__)
    message = ('Unable to import retrofix library.\n'
               'Please install it before install this module.')
    logger.error(message)
    raise Exception(message)

__all__ = [
    'Journal',
    'Group',
    ]
__metaclass__ = PoolMeta


class Journal:
    __name__ = 'account.payment.journal'
    csb58_include_domicile = fields.Boolean('Include Domicile')

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        if ('csb58', 'CSB 58') not in cls.process_method.selection:
            cls.process_method.selection.extend([
                    ('csb58', 'CSB 58'),
                    ])

    @staticmethod
    def default_csb58_include_domicile():
        return False


class Group:
    __name__ = 'account.payment.group'

    def set_default_csb58_payment_values(self):
        values = self.set_default_payment_values()
        values['include_domicile'] = values['payment_journal'].\
            csb58_include_domicile
        values['record_count'] = 0
        values['ordering_records'] = 0
        values['ordering_record_count'] = 0
        for receipt in values['receipts']:
            receipt['reference'] = receipt['party'].code

            if not receipt['address']:
                self.raise_user_error('configuration_error',
                    error_description='party_without_address',
                    error_description_args=(receipt['party'].name,))
            if not receipt['zip'] or not receipt['city'] or \
                    not receipt['country']:
                self.raise_user_error('configuration_error',
                    error_description='party_without_complete_address',
                    error_description_args=(receipt['party'].name,))
        return values

    @classmethod
    def process_csb58(cls, group):
        def set_presenter_header_record():
            record = Record(c58.PRESENTER_HEADER_RECORD)
            record.record_code = '51'
            record.data_code = '70'
            record.nif = values['vat_number']
            record.suffix = values['suffix']
            record.creation_date = values['creation_date']
            record.name = values['company_name']
            record.bank_code = str(values['bank_account'][0:4])
            record.bank_office = str(values['bank_account'][4:8])
            return write([record])

        def set_ordering_header_record():
            record = Record(c58.ORDERING_HEADER_RECORD)
            record.record_code = '53'
            record.data_code = '70'
            record.nif = values['vat_number']
            record.suffix = values['suffix']
            record.creation_date = values['creation_date']
            record.name = values['company_name']
            record.account = values['bank_account']
            record.procedure = '06'
            record.ine = values['ine_code'].zfill(9)
            return write([record])

        def set_required_individual_record():
            record = Record(c58.REQUIRED_INDIVIDUAL_RECORD)
            record.record_code = '56'
            record.data_code = '70'
            record.nif = values['vat_number']
            record.suffix = values['suffix']
            record.reference = receipt['reference']
            record.name = receipt['name']
            record.account = receipt['bank_account']
            record.amount = receipt['amount']
            record.return_code = ''
            record.internal_code = ''
            record.concept = receipt['communication']
            record.due_date = receipt['maturity_date']
            return write([record])

        def set_optional_individual_record():
            record = Record(c58.OPTIONAL_INDIVIDUAL_RECORD)
            record.record_code = '56'
            record.data_code = '71'
            record.nif = values['vat_number']
            record.suffix = values['suffix']
            record.reference = receipt['reference']
            record.concept_2 = ''
            record.concept_3 = ''
            record.concept_4 = ''
            return write([record])

        def set_address_individual_record():
            record = Record(c58.ADDRESS_INDIVIDUAL_RECORD)
            record.record_code = '56'
            record.data_code = '76'
            record.nif = values['vat_number']
            record.suffix = values['suffix']
            record.reference = receipt['reference']
            record.payer_address = receipt['street']
            record.payer_city = receipt['city']
            record.payer_zip = receipt['zip']
            record.ordering_city = values['city']
            record.province_code = values['province']
            record.origin_date = receipt['create_date']
            return write([record])

        def set_ordering_footer_record():
            record = Record(c58.ORDERING_FOOTER_RECORD)
            record.record_code = '58'
            record.data_code = '70'
            record.nif = values['vat_number']
            record.suffix = values['suffix']
            record.amount = values['amount']
            record.payment_line_count = str(values['ordering_records'])
            record.record_count = str(values['ordering_record_count'])
            return write([record])

        def set_presenter_footer_record():
            record = Record(c58.PRESENTER_FOOTER_RECORD)
            record.record_code = '59'
            record.data_code = '70'
            record.nif = values['vat_number']
            record.suffix = values['suffix']
            record.ordering_count = '0001'
            record.amount = values['amount']
            record.payment_line_count = str(values['ordering_records'])
            record.record_count = str(values['record_count'])
            return write([record])

        values = Group.set_default_csb58_payment_values(group)
        text = set_presenter_header_record()
        values['record_count'] += 1
        text += set_ordering_header_record()
        values['record_count'] += 1
        for receipt in values['receipts']:
            text += set_required_individual_record()
            values['record_count'] += 1
            values['ordering_records'] += 1
            if values['include_domicile']:
                text += set_address_individual_record()
                values['record_count'] += 1
                values['ordering_records'] += 1
        values['ordering_record_count'] = values['ordering_records'] + 2
        text += set_ordering_footer_record()
        values['record_count'] += 2
        text += set_presenter_footer_record()
        group.attach_file(text)
