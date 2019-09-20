# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2013 Therp BV (<http://therp.nl>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import logging
from openerp import pooler, SUPERUSER_ID
from openerp.openupgrade import openupgrade, openupgrade_70

logger = logging.getLogger('OpenUpgrade')


def migrate_addresses(cr, pool):
    
    
    cr.execute("ALTER TABLE event_event "
               "DROP CONSTRAINT event_event_location_address_id_fkey")
    
    openupgrade_70.set_partner_id_from_partner_address_id(
        cr, pool, 'event.event',
        'location_address_id', 'location_address_id')

# def migrate_contacts(cr, pool):
#     # Contact id takes precedence over old partner id
#     
#     cr.execute("ALTER TABLE event_event "
#                "DROP CONSTRAINT event_event_location_contact_id_fkey")
#         
#     openupgrade_70.set_partner_id_from_contact_id(
#         cr, pool, 'event_event',
#         'location_contact_id', 'location_contact_id')


def migrate_contacts2(cr, pool):
    # Contact id takes precedence over old partner id

    modeles_champs = [
        # ('event_event', 'responsable_ir_contact_id'),
        # ('event_registration', 'registrered_contact_id'),
        # ('mail_message', 'contact_id'),
        # ('perm_role_allocation', 'contact_id'),
        # ('pir_adhesion', 'contact_communication_id'),
        # ('pir_adhesion', 'contact3_id'),
        # ('pir_adhesion', 'contact1_id_backup'),
        # ('pir_adhesion', 'contact4_id'),
        # ('pir_adhesion', 'contact_adhesion_id'),
        # ('pir_adhesion', 'contact3_id_backup'),
        # ('pir_adhesion', 'contact1_id'),
        # ('pir_adhesion', 'contact_dirigeant_id'),
        # ('pir_adhesion', 'contact2_id_backup'),
        # ('pir_adhesion', 'contact2_id'),
        # ('pir_adhesion', 'contact4_id_backup'),
        # ('pir_adhesion', 'contact_financier_id'),
        # ('pir_carnet_bord', 'contact_id'),
        # ('pir_event_intervenant', 'contact_id'),
        # ('pir_projet', 'pole_contact_id'),
        # ('pir_projet', 'pole_contact2_id'),
        # ('pir_projet', 'cdp_contact_id'),
        # ('pir_projet_etape', 'pole_contact_id'),
        # ('pir_projet_etape', 'pole_contact2_id'),
        # ('pir_projet_structure', 'contact_id')

        # ('crm_lead', 'contact_id'),  # ?? obsolete
        ('event_event', 'responsable_ir_contact_id'),
        ('event_event', 'location_contact_id'),
        ('event_registration', 'registrered_contact_id'),
        ('mail_message', 'contact_id'),
        ('perm_role_allocation', 'contact_id'),
        ('pir_adhesion', 'contact_communication_id'),
        ('pir_adhesion', 'contact3_id'),
        ('pir_adhesion', 'contact1_id_backup'),
        ('pir_adhesion', 'contact4_id'),
        ('pir_adhesion', 'contact_adhesion_id'),
        ('pir_adhesion', 'contact3_id_backup'),
        ('pir_adhesion', 'contact1_id'),
        ('pir_adhesion', 'contact_dirigeant_id'),
        ('pir_adhesion', 'contact2_id_backup'),
        ('pir_adhesion', 'contact2_id'),
        ('pir_adhesion', 'contact4_id_backup'),
        ('pir_adhesion', 'contact_financier_id'),
        ('pir_carnet_bord', 'contact_id'),
        ('pir_event_intervenant', 'contact_id'),
        ('pir_projet', 'pole_contact_id'),
        ('pir_projet', 'pole_contact2_id'),
        ('pir_projet', 'cdp_contact_id'),
        ('pir_projet_etape', 'pole_contact_id'),
        ('pir_projet_etape', 'pole_contact2_id'),
        ('pir_projet_structure', 'contact_id'),
        # ('readhesion_create_list_line', 'contact_adh_id'),
        # ('res_partner', 'contact_adh_id'),
        ('res_partner_address', 'contact_id'),
        # ('res_partner_address', 'contact_adh_id'),
        ('res_partner_contact_category_job', 'contact_id'),
        ('res_partner_job', 'contact_id'),
        ('res_partner_newsletter_subscription', 'contact_id'),
        # ('res_users', 'contact_id'),
    ]

    constraints_champs = [
        # 'event_event_responsable_ir_contact_id_fkey',
        # 'event_registration_registrered_contact_id_fkey',
        # 'perm_role_allocation_contact_id_fkey',
        # 'pir_adhesion_contact_communication_id_fkey',
        # 'pir_adhesion_contact3_id_fkey',
        # 'pir_adhesion_contact1_id_backup_fkey',
        # 'pir_adhesion_contact4_id_fkey',
        # 'pir_adhesion_contact_adhesion_id_fkey',
        # 'pir_adhesion_contact3_id_backup_fkey',
        # 'pir_adhesion_contact1_id_fkey',
        # 'pir_adhesion_contact_dirigeant_id_fkey',
        # 'pir_adhesion_contact2_id_backup_fkey',
        # 'pir_adhesion_contact2_id_fkey',
        # 'pir_adhesion_contact4_id_backup_fkey',
        # 'pir_adhesion_contact_financier_id_fkey',
        # 'pir_carnet_bord_contact_id_fkey',
        # 'pir_event_intervenant_contact_id_fkey',
        # 'pir_projet_pole_contact_id_fkey',
        # 'pir_projet_pole_contact2_id_fkey',
        # 'pir_projet_cdp_contact_id_fkey',
        # 'pir_projet_structure_contact_id_fkey',
        # 'event_event_location_contact_id_fkey'

    'event_event_location_contact_id_fkey',
    'event_event_location_contact_id_fkey',
    'event_event_responsable_ir_contact_id_fkey',
    'event_event_responsable_ir_contact_id_fkey',
    'event_registration_registrered_contact_id_fkey',
    'event_registration_registrered_contact_id_fkey',
    'perm_role_allocation_contact_id_fkey',
    'perm_role_allocation_contact_id_fkey',
    'pir_adhesion_contact1_id_backup_fkey',
    'pir_adhesion_contact1_id_backup_fkey',
    'pir_adhesion_contact1_id_fkey',
    'pir_adhesion_contact1_id_fkey',
    'pir_adhesion_contact2_id_backup_fkey',
    'pir_adhesion_contact2_id_backup_fkey',
    'pir_adhesion_contact2_id_fkey',
    'pir_adhesion_contact2_id_fkey',
    'pir_adhesion_contact3_id_backup_fkey',
    'pir_adhesion_contact3_id_backup_fkey',
    'pir_adhesion_contact3_id_fkey',
    'pir_adhesion_contact4_id_backup_fkey',
    'pir_adhesion_contact4_id_fkey',
    'pir_adhesion_contact_adhesion_id_fkey',
    'pir_adhesion_contact_communication_id_fkey',
    'pir_adhesion_contact_dirigeant_id_fkey',
    'pir_adhesion_contact_financier_id_fkey',
    'pir_carnet_bord_contact_id_fkey',
    'pir_contact_category_contact_id_fkey',
    'pir_contact_category_job_contact_id_fkey',
    'pir_contact_category_partner_contact_id_fkey',
    'pir_contact_create_list_contact_contact_id_fkey',
    'pir_contact_departement_partner_contact_id_fkey',
    'pir_contact_list_contact_contact_id_fkey',
    'pir_contact_region_partner_contact_id_fkey',
    'pir_event_intervenant_contact_id_fkey',
    'pir_projet_cdp_contact_id_fkey',
    'pir_projet_pole_contact2_id_fkey',
    'pir_projet_pole_contact_id_fkey',
    'pir_projet_structure_contact_id_fkey',
    'res_partner_contact_category_job_contact_id_fkey',
    'res_partner_contact_mailing_list_rel_contact_id_fkey',
    'res_partner_job_contact_id_fkey',
    ]

    for modele in modeles_champs:
        logger.info('event/post-mig  %s.%s' % modele)
        constraint = "%s_%s_fkey" %(modele[0], modele[1])
        if constraint in constraints_champs:
            cr.execute("ALTER TABLE "+modele[0]+" "
                       "DROP CONSTRAINT "+constraint+" ")

        openupgrade_70.set_partner_id_from_contact_id(
            cr, pool, modele[0],
            modele[1], modele[1])


@openupgrade.migrate()
def migrate(cr, version):
    pool = pooler.get_pool(cr.dbname)
    logger.info("event/post-mig-%s : MIGRATING EVENT ADDRESSES IDS... " % version)
    migrate_addresses(cr, pool)
    logger.info("event/post-mig-%s : MIGRATING CONTACTS IDS...." % version)
    # migrate_contacts(cr, pool)
    migrate_contacts2(cr, pool)
