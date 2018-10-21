## coding: utf-8
# This file is part of account_payment_es_csb_58 module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval
import logging
import banknumber

try:
    from retrofix import c58
    from retrofix.record import Record, write as retrofix_write
except ImportError:
    logger = logging.getLogger(__name__)
    message = ('Unable to import retrofix library.\n'
               'Please install it before install this module.')
    logger.error(message)
    raise Exception(message)

__all__ = [
    'BankAccount',
    'Journal',
    'Group',
    ]

province = {
    'none': '',
    'ES-VI': '01',
    'ES-AB': '02',
    'ES-A': '03',
    'ES-AL': '04',
    'ES-AV': '05',
    'ES-BA': '06',
    'ES-PM': '07',
    'ES-B': '08',
    'ES-BU': '09',
    'ES-CC': '10',
    'ES-CA': '11',
    'ES-CS': '12',
    'ES-CR': '13',
    'ES-CO': '14',
    'ES-C': '15',
    'ES-CU': '16',
    'ES-GI': '17',
    'ES-GR': '18',
    'ES-GU': '19',
    'ES-SS': '20',
    'ES-H': '21',
    'ES-HU': '22',
    'ES-J': '23',
    'ES-LE': '24',
    'ES-L': '25',
    'ES-LO': '26',
    'ES-LU': '27',
    'ES-M': '28',
    'ES-MA': '29',
    'ES-MU': '30',
    'ES-NA': '31',
    'ES-OR': '32',
    'ES-O': '33',
    'ES-P': '34',
    'ES-GC': '35',
    'ES-PO': '36',
    'ES-SA': '37',
    'ES-TF': '38',
    'ES-S': '39',
    'ES-SG': '40',
    'ES-SE': '41',
    'ES-SO': '42',
    'ES-T': '43',
    'ES-TE': '44',
    'ES-TO': '45',
    'ES-V': '46',
    'ES-VA': '47',
    'ES-BI': '48',
}


class BankAccount(metaclass=PoolMeta):
    __name__ = 'bank.account'

    def get_first_other_number(self):
        iban = None
        for number in self.numbers:
            if number.type == 'other':
                return number.number
            elif not iban and number.type == 'iban':
                iban = number.number
        if iban:
            return iban[4:].replace(' ', '')
        return None


class Journal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'
    csb58_include_domicile = fields.Boolean('Include Domicile')

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        if ('csb58', 'CSB 58') not in cls.process_method.selection:
            cls.process_method.selection.extend([
                    ('csb58', 'CSB 58'),
                    ])

        if 'invisible' not in cls.sepa_bank_account_number.states:
            cls.sepa_bank_account_number.states['invisible'] = (
                Eval('process_method') != 'csb58')
        else:
            cls.sepa_bank_account_number.states['invisible'] &= (
                Eval('process_method') != 'csb58')

        if 'required' not in cls.sepa_bank_account_number.states:
            cls.sepa_bank_account_number.states['required'] = (
                Eval('process_method') == 'csb58')
        else:
            cls.sepa_bank_account_number.states['required'] |= (
                Eval('process_method') == 'csb58')

    @staticmethod
    def default_csb58_include_domicile():
        return False

    @classmethod
    def view_attributes(cls):
        return super(Journal, cls).view_attributes() + [
            ('//group[@id="csb_58"]', 'states', {
                    'invisible': Eval('process_method') != 'csb58',
                    })]


class Group(metaclass=PoolMeta):
    __name__ = 'account.payment.group'

    @classmethod
    def __setup__(cls):
        super(Group, cls).__setup__()
        cls._error_messages.update({
                'company_without_complete_address': ('The company %s has no a '
                    'complete address to add to the file.'),
                'party_without_address': ('The party %s has no any address to '
                    'add to the file'),
                'party_without_complete_address': ('The party %s has no a '
                    'complete address to build the file.'),
                'party_without_province': ('The party %s has no any province '
                    'assigned at its address'),
                'party_without_vat_number': ('The party %s has no any vat '
                    'number.'),
                'no_lines': ('Can not generate export file, there are not '
                    'payment lines.'),
                'bank_account_not_defined': ('The bank account of the company '
                    '%s is not defined.'),
                'wrong_bank_account': ('The bank account number of the '
                    'company %s is not correct.'),
                'vat_number_not_defined': ('The company have not any VAT '
                    'number defined.'),
                'customer_bank_account_not_defined': ('The bank account '
                    'number of the party %s is not defined and current payment'
                    ' journal enforces all lines to have a bank account.'),
                'wrong_party_bank_account': ('The bank account number of the '
                    'party %s is not correct.'),
                'wrong_payment_journal': ('The payment journal has no norm to '
                    'build a file.'),
                'unknown_error': ('Unknown error. An error occurred creating '
                    'the file.'),
                'remittance': 'remittance',
                'configuration_error': ('Configuration Error!'),
                'payment_without_bank_account': (
                    'The payment "%s" doesn\'t have bank account.'),
                'party_without_bank_account': (
                    'The party "%s" doesn\'t have bank account.'),
                })

    def set_default_csb58_payment_values(self):
        pool = Pool()
        Party = pool.get('party.party')
        Date = pool.get('ir.date')
        today = Date.today()
        values = {}
        journal = self.journal
        values['payment_journal'] = journal
        values['party'] = journal.party
        values['name'] = values['party'].name

        # Checks bank account code.
        bank_account = journal.sepa_bank_account_number.account
        if not bank_account:
            self.raise_user_error('configuration_error',
                error_description='bank_account_not_defined',
                error_description_args=(values['name']))
        code = bank_account.get_first_other_number()
        if not code or not banknumber.check_code('ES', code):
            self.raise_user_error('configuration_error',
                        error_description='wrong_bank_account',
                        error_description_args=(values['name'],))

        # Checks vat number
        vat = journal.party and journal.party.vat_number \
            or False
        if not vat:
            self.raise_user_error('configuration_error',
                        error_description='vat_number_not_defined',
                        error_description_args=(values['name']))

        # Checks whether exists lines
        payments = self.payments
        if not payments:
            self.raise_user_error('no_lines')

        values['number'] = str(self.id)
        values['payment_date'] = self.planned_date if self.planned_date \
            else today
        values['creation_date'] = today
        values['vat_number'] = vat
        values['suffix'] = journal.suffix
        values['company_name'] = journal.company.party.name
        values['bank_account'] = code
        values['ine_code'] = journal.ine_code
        values['amount'] = 0

        values['address'] = Party.address_get(values['party'], type='invoice')
        if values['address']:
            values['street'] = values['address'].street
            values['zip'] = values['address'].zip
            values['city'] = values['address'].city
            values['subdivision'] = values['address'].subdivision or False
            values['province'] = province[values['subdivision'].code
                    if (values['subdivision']
                        and values['subdivision'].type == 'province')
                    else 'none']

        receipts = []
        if self.join:
            parties_bank_accounts = {}
            # Join all receipts of the same party and bank_account
            for payment in payments:
                key = (payment.party, payment.bank_account)
                if key not in parties_bank_accounts:
                    parties_bank_accounts[key] = [payment]
                else:
                    parties_bank_accounts[key].append(payment)
            for party_bank_account in parties_bank_accounts:
                if not party_bank_account or not party_bank_account[1]:
                    self.raise_user_error('party_without_bank_account',
                        party_bank_account and party_bank_account[0]
                            and party_bank_account[0].rec_name)
                amount = 0
                communication = ''
                date = False
                maturity_date = today
                create_date = False
                date_created = False
                invoices = []
                for payment in parties_bank_accounts[party_bank_account]:
                    amount += payment.amount
                    communication += '%s %s' % (payment.id,
                        payment.description)
                    if not date or date < payment.date:
                        date = payment.date
                    if payment.line:
                        if (not maturity_date
                                or maturity_date < payment.line.maturity_date):
                            maturity_date = payment.line.maturity_date
                        invoices.append(payment.line.origin)
                    if not create_date or create_date < payment.create_date:
                        create_date = payment.create_date
                    if not date_created or date_created < payment.date:
                        date_created = payment.date

                vals = {
                    'party': party_bank_account[0],
                    'bank_account':
                        party_bank_account[1].get_first_other_number(),
                    'invoices': invoices,
                    'amount': amount,
                    'communication': communication,
                    'date': date,
                    'maturity_date': maturity_date,
                    'create_date': create_date,
                    'date_created': date_created,
                    'vat_number': party_bank_account[0].vat_number,
                    }
                address = Party.address_get(party_bank_account[0],
                    type='invoice')
                if address:
                    vals['name'] = vals['party'].name
                    vals['address'] = address
                    vals['street'] = address.street or False
                    vals['streetbis'] = address.streetbis or False
                    vals['zip'] = address.zip or False
                    vals['city'] = address.city or False
                    vals['country'] = address.country or False
                    if vals['country']:
                        vals['country_code'] = (vals['country'].code
                            or False)
                    vals['subdivision'] = address.subdivision or False
                    vals['state'] = (vals['subdivision']
                            and vals['subdivision'].name or '')
                    vals['province'] = province[vals['subdivision'].code
                            if (vals['subdivision']
                                and vals['subdivision'].type == 'province')
                            else 'none']
                receipts.append(vals)
                values['amount'] += abs(amount)
        else:
            # Each payment is a receipt
            for payment in payments:
                if not payment.bank_account:
                    self.raise_user_error('payment_without_bank_account',
                        payment.rec_name)
                party = payment.party
                amount = payment.amount
                vals = {
                    'party': party,
                    'bank_account':
                        payment.bank_account.get_first_other_number(),
                    'invoices': [payment.line and payment.line.origin or None],
                    'amount': amount,
                    'communication': '%s %s' % (payment.id,
                        payment.description),
                    'date': payment.date,
                    'maturity_date': (payment.line
                        and payment.line.maturity_date or today),
                    'create_date': payment.create_date,
                    'date_created': payment.date,
                    'vat_number': party.vat_number,
                    }
                address = Party.address_get(party, type='invoice')
                if address:
                    vals['name'] = vals['party'].name
                    vals['address'] = address
                    vals['street'] = address.street or False
                    vals['streetbis'] = address.streetbis or False
                    vals['zip'] = address.zip or False
                    vals['city'] = address.city or False
                    vals['country'] = address.country or False
                    if vals['country']:
                        vals['country_code'] = vals['country'].code or False
                    vals['subdivision'] = address.subdivision or False
                    if vals['subdivision']:
                        vals['state'] = vals['subdivision'].name or ''
                    vals['province'] = province[vals['subdivision'].code
                            if (vals['subdivision']
                                and vals['subdivision'].type == 'province')
                            else 'none']
                receipts.append(vals)
                values['amount'] += abs(amount)
        if journal.require_bank_account:
            for receipt in receipts:
                if not receipt['bank_account']:
                    self.raise_user_error('configuration_error',
                        error_description='customer_bank_account_not_defined',
                        error_description_args=(receipt['name'],))
                if not banknumber.check_code('ES', receipt['bank_account']):
                    self.raise_user_error('configuration_error',
                        error_description='wrong_party_bank_account',
                        error_description_args=(receipt['name'],))
        values['receipts'] = receipts
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

    def attach_file(self, data):
        IrAttachment = Pool().get('ir.attachment')
        journal = self.journal
        values = {
            'name': '%s_%s_%s' % (
                self.raise_user_error('remittance', raise_exception=False),
                journal.process_method, self.reference),
            'type': 'data',
            'data': data,
            'resource': '%s' % (self),
            }
        IrAttachment.create([values])

    @classmethod
    def process_csb58(cls, group):
        def set_presenter_header_record():
            record = Record(c58.PRESENTER_HEADER_RECORD)
            record.record_code = '51'
            record.data_code = '70'
            record.nif = values['vat_code']
            record.suffix = values['suffix']
            record.creation_date = values['creation_date']
            record.name = values['company_name']
            record.bank_code = str(values['bank_account'][0:4])
            record.bank_office = str(values['bank_account'][4:8])
            return retrofix_write([record])

        def set_ordering_header_record():
            record = Record(c58.ORDERING_HEADER_RECORD)
            record.record_code = '53'
            record.data_code = '70'
            record.nif = values['vat_code']
            record.suffix = values['suffix']
            record.creation_date = values['creation_date']
            record.name = values['company_name']
            record.account = values['bank_account']
            record.procedure = '06'
            record.ine = values['ine_code'].zfill(9)
            return retrofix_write([record])

        def set_required_individual_record():
            record = Record(c58.REQUIRED_INDIVIDUAL_RECORD)
            record.record_code = '56'
            record.data_code = '70'
            record.nif = values['vat_code']
            record.suffix = values['suffix']
            record.reference = receipt['reference']
            record.name = receipt['name']
            record.account = receipt['bank_account']
            record.amount = receipt['amount']
            record.return_code = ''
            record.internal_code = ''
            record.concept = receipt['communication']
            record.due_date = receipt['maturity_date']
            return retrofix_write([record])

        def set_optional_individual_record():
            record = Record(c58.OPTIONAL_INDIVIDUAL_RECORD)
            record.record_code = '56'
            record.data_code = '71'
            record.nif = values['vat_code']
            record.suffix = values['suffix']
            record.reference = receipt['reference']
            record.concept_2 = ''
            record.concept_3 = ''
            record.concept_4 = ''
            return retrofix_write([record])

        def set_address_individual_record():
            record = Record(c58.ADDRESS_INDIVIDUAL_RECORD)
            record.record_code = '56'
            record.data_code = '76'
            record.nif = values['vat_code']
            record.suffix = values['suffix']
            record.reference = receipt['reference']
            record.payer_address = receipt['street']
            record.payer_city = receipt['city']
            record.payer_zip = receipt['zip']
            record.ordering_city = values['city']
            record.province_code = values['province']
            record.origin_date = receipt['create_date']
            return retrofix_write([record])

        def set_ordering_footer_record():
            record = Record(c58.ORDERING_FOOTER_RECORD)
            record.record_code = '58'
            record.data_code = '70'
            record.nif = values['vat_code']
            record.suffix = values['suffix']
            record.amount = values['amount']
            record.payment_line_count = str(values['ordering_records'])
            record.record_count = str(values['ordering_record_count'])
            return retrofix_write([record])

        def set_presenter_footer_record():
            record = Record(c58.PRESENTER_FOOTER_RECORD)
            record.record_code = '59'
            record.data_code = '70'
            record.nif = values['vat_code']
            record.suffix = values['suffix']
            record.ordering_count = '0001'
            record.amount = values['amount']
            record.payment_line_count = str(values['ordering_records'])
            record.record_count = str(values['record_count'])
            return retrofix_write([record])

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
