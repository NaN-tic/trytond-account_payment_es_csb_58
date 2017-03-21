# This file is part of account_payment_es_csb_58 module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import payment


def register():
    Pool.register(
        payment.BankAccount,
        payment.Journal,
        payment.Group,
        module='account_payment_es_csb_58', type_='model')
