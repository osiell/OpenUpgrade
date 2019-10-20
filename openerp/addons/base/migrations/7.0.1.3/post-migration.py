# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This migration script copyright (C) 2012-2013 Therp BV (<http://therp.nl>)
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

from openupgrade import openupgrade
from openerp import pooler, SUPERUSER_ID
from openerp.osv import osv
import psycopg2
#from gi.overrides.GLib import attr
import sys

def info(*msgs):
    for msg in msgs:
        print(msg)
    sys.stdout.flush()

force_defaults = {
    'ir.mail_server': [('active', True)],
    'ir.model.access': [('active', True)],
    'res.company': [('custom_footer', True)],
    # We'll have to adapt the default for is_company in specific
    # modules. For instance, a migration script for hr
    # could reset is_company for partners associated with
    # employees
    'res.partner': [('is_company', True)],
}


def migrate_ir_translation(cr):
    openupgrade.logged_query(
        cr,
        """ UPDATE ir_translation
            SET state = 'translated'
            WHERE length(value) > 0;
        """)
    openupgrade.logged_query(
        cr,
        """ UPDATE ir_translation
            SET state = 'to_translate'
            WHERE state is NULL;
        """)


def migrate_company(cr):
    """
    Copy char value to new text column
    """
    cr.execute(
        """ UPDATE res_company
            SET rml_footer = rml_footer1
        """)


def migrate_contact(cr, pool):

    partner_obj = pool.get('res.partner')

    cr.execute(
        "ALTER TABLE res_partner_contact "
        "ADD column openupgrade_7_migrated_to_partner_id "
        " INTEGER")

    cr.execute(
    "ALTER TABLE res_partner "
    "ADD column openupgrade_7_migrated_from_contact_id "
    " INTEGER")

    cr.execute(
        "ALTER TABLE res_partner_contact ADD FOREIGN KEY "
        "(openupgrade_7_migrated_to_partner_id) "
        "REFERENCES res_partner ON DELETE SET NULL")

    fields = ['id', 'function', 'sequence_partner', 'address_id', 'fax', 'extension', 'sequence_contact', 'date_start', 'date_stop',
              'contact_id', 'phone', 'state', 'other', 'email', 'id_sfl', 'id_adherent', 'mobile', 'default_ok', 'actif_ok', 'active',
              'fax_e164', 'mobile_e164', 'phone_e164', 'count_phone_dials']

    cr.execute(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_name = 'res_partner';")
    partner_fields = [i[0] for i in cr.fetchall()]

    def get_contact_fields(fields_list):
        cr.execute(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_name = 'res_partner_contact';")
        available_fields = set(i[0] for i in cr.fetchall())
        lost_fields = set(fields_list) - available_fields
        info('## lost fields (res_partner_contact) ##', lost_fields)
        # keep fields that are found in res_partner // to avoid crash
        return available_fields.intersection(fields_list)

    fields_contact = get_contact_fields(partner_fields)
    info('## contact fields ##',fields_contact)

    def set_contact_partner(contact_id, partner_id):
        cr.execute(
            "UPDATE res_partner_contact "
            "SET openupgrade_7_migrated_to_partner_id = %s "
            "WHERE id = %s" %
            (partner_id, contact_id))

    def create_partner(cr, contact_id, vals, partner_address_id, already_contact):
        """
        Create a partner from a contact. Update the vals
        with the defaults only if the keys do not occur
        already in vals. Register the created partner_id
        on the obsolete contact table
        """

        vals['contact_type'] = 'standalone'
        contact_id_bis = vals.pop('id') 

        partner_id = partner_obj.create(cr, SUPERUSER_ID, vals)
        vals['partner_id'] = partner_id
        vals['id'] = contact_id_bis

        partner_id = int(partner_id)

        # partner_obj.write(cr, SUPERUSER_ID, [partner_id], {
        #     'parent_id': parent_id})
        # set_address_partner(address_id, partner_id)

        #print("PARTNER ID :", partner_id)
        if partner_address_id != False:
            #partner_obj.write(cr, SUPERUSER_ID, [partner_id], {'contact_type': 'attached'})
            cr.execute("UPDATE res_partner "
                       "SET contact_type='attached' "
                       "WHERE id=%s" % (partner_id,))
            if partner_address_id not in already_contact:
                cr.execute("UPDATE res_partner "
                           "SET contact_id=%s "
                           "WHERE id=%s " % (partner_id,partner_address_id))
                # FIXME (Code fonctionnel quand on pourra utiliser contact_id et other_contact_ids; leur utilisation peut être vérifiée avec hasattr()
                #partner_obj.write(cr, SUPERUSER_ID, [partner_address_id],
                                  #{'contact_id': partner_id})
            #else:
                #partner_obj.write(cr, SUPERUSER_ID, [partner_address_id],
                                  #{'other_contact_ids': ([6,0,partner_id])})
        set_contact_partner(contact_id, partner_id)
        return partner_id

    def set_function(partner_address_id, function):
        partner_obj.write(cr, SUPERUSER_ID, [partner_address_id],
                          {'function': function})


    def load_contact_vals(cr, contact_id, fields):
        query = ("SELECT " + ', '.join(fields) + "\n"
            "FROM res_partner_contact\n"
            "WHERE id = %s"
            )
        cr.execute(query % (contact_id,))
        row_values = cr.fetchall()
        for row in row_values:
            row_selected = [val or False for val in row]
            dict_values = dict(zip(fields,row_selected))
        #print("OLD CONTACT VALS : ", dict_values)
        return dict_values

    def get_address_partner_id(cr, old_address_id):
        query = ("SELECT openupgrade_7_migrated_to_partner_id "
            "FROM res_partner_address "
            "WHERE id = %s"
            )
        cr.execute(query%(old_address_id,))
        row_values = cr.fetchall()
        for row in row_values:
            new_id = row[0]
        #print("NEW ID :", new_id)
        return new_id


    def proccess_contact(cr, pool, fields, whereclause, args=None ):
        cr.execute(
            ("SELECT " + ', '.join(fields) + "\n"
            "FROM res_partner_job\n"
            "WHERE " + whereclause) % (args or []))
        row_values = cr.fetchall()
        already_contact = []
        contact_created = []


        for row in row_values:
            # default
            contact_vals = {}
            partner_address_id = False

            row_selected = [val or False for val in row]
            dict_values = dict(zip(fields,row_selected))

            if dict_values['address_id'] != False:
                partner_address_id = get_address_partner_id(cr, dict_values['address_id'])
            if dict_values['contact_id'] != False:
                contact_vals = load_contact_vals(cr, dict_values['contact_id'], fields_contact)
                create_partner(cr, dict_values['contact_id'], contact_vals, partner_address_id, already_contact)
                contact_created.append(dict_values['contact_id'])
                already_contact.append(partner_address_id)
            if partner_address_id:
                set_function(partner_address_id, dict_values['function'])

        # (Prévu por le reste des contacts non migrés)
        cr.execute(
            "SELECT id," + ', '.join(fields_contact) + "\n"
            "FROM res_partner_contact\n"
            "WHERE openupgrade_7_migrated_to_partner_id IS null\n"
        )
        row_values =  cr.fetchall()
        for row in row_values:
            row_selected = [val or False for val in row]
            dict_values = dict(zip(fields, row_selected))

            if dict_values['id'] not in contact_created:
                create_partner(cr, dict_values['id'], contact_vals, False, already_contact)


    proccess_contact(cr, pool, fields, "id is not null")


def migrate_base_contact(cr):
    """
    In v6.1, base_contact module has this structure:

    res.partner
    |
    |-> res.partner.address -|
    |-> res.partner.address -|
                             |-> res.partner.contact
    res.partner              |
    |                        |
    |-> res.partner.address -|

    And res.partner.contact contains information that is shared to linked
    res.partner.address via related fields.

    In v7, now that we remove res.partner.contact, we should copy
    res.partner.contact information on each linked address (that has been
    converted also to a res.partner record), but not create a new res.partner
    for each res.partner.contact. There's a special case where
    res.partner.address has been merged with main res.partner because it's
    the first available address. In that case, we still have to create a new
    res.partner.
    """
    cr.execute(
        "SELECT * FROM ir_module_module "
        "WHERE name = 'base_contact' and state = 'to remove';")
    if not cr.fetchall():
        return
    # Add a column to reference the contact
    cr.execute(
        "ALTER TABLE res_partner "
        "ADD column openupgrade_7_migrated_from_contact_id "
        " INTEGER")
    cr.execute(
        "ALTER TABLE res_partner ADD FOREIGN KEY "
        "(openupgrade_7_migrated_from_contact_id) "
        "REFERENCES res_partner_contact ON DELETE SET NULL")
    # Add non-existing columns that can be used with partner_lastname module
    cr.execute("ALTER TABLE res_partner "
               "ADD COLUMN firstname character varying;")
    cr.execute("ALTER TABLE res_partner "
               "ADD COLUMN lastname character varying;")
    # Update addresses that are still "contacts" with the contact information
    openupgrade.logged_query(
        cr,
        """
        UPDATE
            res_partner
        SET
            name=contact.name,
            lastname=contact.last_name,
            firstname=contact.first_name,
            mobile=contact.mobile,
            image=contact.photo,
            website=contact.website,
            lang=res_lang.code,
            active=contact.active,
            comment=contact.comment,
            country_id=contact.country_id,
            email=contact.email,
            birthdate=contact.birthdate,
            openupgrade_7_migrated_from_contact_id=contact.id
        FROM
            res_lang,
            res_partner_contact contact,
            res_partner_address
        WHERE
            res_lang.id = contact.lang_id AND
            res_partner.id =
                res_partner_address.openupgrade_7_migrated_to_partner_id AND
            contact.id = res_partner_address.contact_id AND
            res_partner.parent_id IS NOT NULL;
        """)
    # Create the rest of the contacts as res.partner records
    openupgrade.logged_query(
        cr,
        """
        INSERT INTO res_partner
            (name, lastname, firstname, mobile, image, website, lang, active,
             comment, country_id, email, birthdate, parent_id, street, street2,
             city, zip, state_id, customer, supplier, function,
             openupgrade_7_migrated_from_contact_id)
        SELECT
            contact.name,
            contact.last_name,
            contact.first_name,
            contact.mobile,
            contact.photo,
            contact.website,
            res_lang.code,
            contact.active,
            contact.comment,
            contact.country_id,
            contact.email,
            contact.birthdate,
            res_partner.id,
            res_partner.street,
            res_partner.street2,
            res_partner.city,
            res_partner.zip,
            res_partner.state_id,
            res_partner.customer,
            res_partner.supplier,
            res_partner_address.function,
            contact.id
        FROM
            res_partner,
            res_partner_contact contact,
            res_partner_address,
            res_lang
        WHERE
            res_lang.id = contact.lang_id AND
            res_partner.id =
                res_partner_address.openupgrade_7_migrated_to_partner_id AND
            contact.id = res_partner_address.contact_id AND
            res_partner.parent_id IS NULL;
        """)


def migrate_partner_address(cr, pool):
    """ res.partner.address is obsolete. Move existing data to
    partner
    """
    info("MIGRATE PARTNER ADDRESS")
    partner_obj = pool.get('res.partner')
    cr.execute(
        "ALTER TABLE res_partner_address "
        "ADD column openupgrade_7_migrated_to_partner_id "
        " INTEGER")
    cr.execute(
        "ALTER TABLE res_partner "
        "ADD column openupgrade_7_migrated_from_address_id "
        " INTEGER")
    cr.execute(
        "ALTER TABLE res_partner_address ADD FOREIGN KEY "
        "(openupgrade_7_migrated_to_partner_id) "
        "REFERENCES res_partner ON DELETE SET NULL")
    cr.execute(
        "ALTER TABLE res_partner_address "
        "ADD column openupgrade_7_address_processed "
        " BOOLEAN")
    # To fix bug where category_id is not yet created after module update
    cr.execute(
        "ALTER TABLE res_partner "
        "ADD column category_id "
        " INTEGER")
    fields = [
        'id', 'birthdate', 'city', 'country_id', 'email', 'fax', 'function',
        'mobile', 'phone', 'state_id', 'street', 'street2', 'type', 'zip',
        'partner_id', 'name', 'company_id'
    ]
    # propagate_fields = [
    #     'lang', 'tz', 'customer', 'supplier',
    # ]
    partner_found = []
    processed_ids = []

    # Make sure fields exist
    cr.execute(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_name = 'res_partner_address';")
    available_fields = set(i[0] for i in cr.fetchall())
    lost_fields = set(fields) - available_fields
    fields = available_fields.intersection(fields)

    def set_address_partner(address_id, partner_id):
        cr.execute(
            "UPDATE res_partner_address "
            "SET openupgrade_7_migrated_to_partner_id = %s "
            "WHERE id = %s" %
            (partner_id, address_id))

    def set_partner_address(address_id, partner_id):#Pas utilisé
        cr.execute(
            "UPDATE res_partner "
            "SET parent_id = %s "
            "WHERE id = %s" %
            (partner_id, address_id))

    def set_address_processed(processed_ids):
        while processed_ids:
            ids = processed_ids[:2000]
            del processed_ids[:2000]
            cr.execute(
                "UPDATE res_partner_address "
                "SET openupgrade_7_address_processed = True "
                "WHERE id in %s" % (tuple(ids),))

    def create_partner_w_addr(vals):
        """
        Create a partner from an address. Update the vals
        with the defaults only if the keys do not occur
        already in vals. Register the created partner_id
        on the obsolete address table
        """
        parent_id = vals.pop('partner_id')
        address_id = vals.pop('id')
        vals['parent_id'] = parent_id
        partner_id = partner_obj.create(cr, SUPERUSER_ID, vals)
        set_address_partner(address_id, partner_id)
        vals['partner_id'] = partner_id
        # vals.pop('parent_id')
        vals['id'] = address_id
        return partner_id

    def process_address_type(cr, pool, fields, whereclause, args=None):
        """
        Migrate addresses to partners, based on sql WHERE clause
        """
        # Mass process Dangling addresses, create with not is_company
        # not supplier and not customer
        info('migrate addresses to partners where %s' % whereclause)

        # Select distinct must be a first column
        fields.remove('partner_id')
        fields = list(fields)
        fields[:0] = ["partner_id"]
        # openupgrade.logged_query(
        #     cr, "\n"
        cr.execute(
            ("SELECT " + ', '.join(fields) + "\n"
            "FROM res_partner_address\n"
            "WHERE " + whereclause) % (args or ()))
        rows_values = cr.fetchall()
        partner_store_update = []
        partner_store_insert = []
        for row in rows_values:
            row_cleaned = [val or False for val in row]
            dict_values = dict(zip(fields, row_cleaned))
            if dict_values['name'] == False:
                dict_values['name'] = ''
            create_partner_w_addr(dict_values)
            # others fields will be added with sql queries
            dict_values['openupgrade_7_migrated_from_address_id'] = \
                dict_values['id']
            values = {}

            partner_defaults = {
                # list of values that we should not overwrite
                # in existing partners
                'customer': False,
                'is_company': dict_values['type'] != 'contact',
                'type': dict_values['type'],
                'name': dict_values['name'] or '/',
                'parent_id' : dict_values['partner_id']
            }

            if not dict_values['partner_id']:
                for f in ['name', 'id', 'type', 'partner_id']:
                    del dict_values[f]
                for key in partner_defaults:
                    if key not in dict_values:
                        dict_values[key] = partner_defaults[key]
                values = partner_obj._add_missing_default_values(
                    cr, SUPERUSER_ID, dict_values)
                partner_store_insert.append(values)
            else:
                if dict_values['partner_id'] not in partner_found:
                    for f in ['name', 'id', 'type']:
                        del dict_values[f]
                    dict_values['id'] = dict_values['partner_id']
                    del dict_values['partner_id']
                    values = dict_values
                    partner_found.append(values['id'])
                    partner_store_update.append(values)
                else:
                    dict_values.update({'is_company': False})
                    for f in ['name', 'id', 'type', 'partner_id']:
                        del dict_values[f]
                    for key in partner_defaults:
                        if key not in dict_values:
                            dict_values[key] = partner_defaults[key]
                    values = partner_obj._add_missing_default_values(
                        cr, SUPERUSER_ID, dict_values)
                    partner_store_insert.append(values)
            processed_ids.append(
                values['openupgrade_7_migrated_from_address_id'])

        openupgrade.logged_query(
            cr, "\n"
            "UPDATE res_partner part "
            "SET openupgrade_7_migrated_from_address_id = addr.id "
            "FROM res_partner_address addr "
            "WHERE part.id = addr.openupgrade_7_migrated_to_partner_id")
        # Update propagate_fields from partner parent
        # TODO Use propagate_fields = [ 'lang', 'tz', 'customer', 'supplier',]
        # to generate this query
        openupgrade.logged_query(
            cr, "\n"
            "UPDATE res_partner part "
            "SET lang = parent.lang, "
            "tz = parent.tz, "
            "customer = parent.customer, "
            "supplier = parent.supplier "
            "FROM res_partner parent "
            "WHERE part.parent_id = parent.id "
            " AND part.parent_id IS NOT NULL"
            " AND part.openupgrade_7_migrated_from_address_id IS NOT NULL")
        # set_address_partner by mass update
        openupgrade.logged_query(
            cr, "\n"
            "UPDATE res_partner_address addr "
            "SET openupgrade_7_migrated_to_partner_id = part.id "
            "FROM res_partner part "
            "WHERE addr.id = part.openupgrade_7_migrated_from_address_id"
            " AND openupgrade_7_migrated_to_partner_id IS NULL")

    # Process all addresses, default type first
    process_address_type(cr, pool, fields.copy(), "id is not NULL")
    set_address_processed(processed_ids)

    # Cas gérés dans le cas ci-dessus 
#     # then try the ones without type and without name
#     #process_address_type(
#      #   cr, pool, fields.copy(),
#       #  "(type IS NULL OR type = '') AND (name IS NULL OR name = '')")
#     # and only then just without type
#     #process_address_type(
#       #  cr, pool, fields.copy(),
#      #   "(type IS NULL OR type = '') AND name <> ''")
#     # Not in clause is very slow. we replace them by an ubptade on a new column
#     #set_address_processed(processed_ids)
#     #process_address_type(
#       #  cr, pool, fields.copy(),
#      #   "openupgrade_7_address_processed IS NULL ")
# 
    # Check that all addresses have been migrated
    cr.execute(
        "SELECT COUNT(*) FROM res_partner_address "
        "WHERE openupgrade_7_migrated_to_partner_id is NULL ")
    assert(not cr.fetchone()[0])


def update_users_partner(cr, pool):
    """
    Now that the fields exist on the model, finish
    the work of create_users_partner() in the pre script
    """
    partner_obj = pool.get('res.partner')
    cr.execute(
        # Can't use orm as these fields do not appear on the model
        # anymore
        "SELECT id, openupgrade_7_created_partner_id, context_lang, "
        "context_tz, " + openupgrade.get_legacy_name('user_email') + " "
        "FROM res_users "
        "WHERE openupgrade_7_created_partner_id IS NOT NULL")
    for row in cr.fetchall():
        partner_vals = {
            'user_ids': [(4, row[0])],
            'lang': row[2] or False,
            'tz': row[3] or False,
            'email': row[4] or False,
        }
        partner_obj.write(cr, SUPERUSER_ID, row[1], partner_vals)


def reset_currency_companies(cr, pool):
    """
    Having a company on currencies affects multicompany databases
    https://bugs.launchpad.net/openobject-server/+bug/1111298
    """
    currency_ids = pool.get('res.currency').search(
        cr, SUPERUSER_ID, [('company_id', '!=', False)],
        context={'active_test': False})
    pool.get('res.currency').write(
        cr, SUPERUSER_ID, currency_ids,
        {'company_id': False})


def migrate_res_company_logo(cr, pool):
    """
    Transfert logo from res_company to res_partner linked to the res_company,
    according to the new behaviour of V7:
    'res_company.logo' is now a field reladed to 'res_partner.image'
    """
    partner_obj = pool.get('res.partner')
    cr.execute("""
        SELECT partner_id, %s
        FROM res_company
        WHERE %s is not null""" % (
        openupgrade.get_legacy_name('logo'),
        openupgrade.get_legacy_name('logo')))
    for row in cr.fetchall():
        vals = {'image': row[1]}
        partner_obj.write(cr, SUPERUSER_ID, row[0], vals)


def _prepare_insert(pool, partner_val, cols):
        """ Apply column formating to prepare data for SQL inserting
        Return a copy of partner
        """
        partner_obj = pool.get('res.partner')
        st_copy = partner_val
        for k, col in st_copy.iteritems():
            if k in cols:
                if k not in ['id', 'openupgrade_7_migrated_from_address_id']:
                    st_copy[k] = partner_obj._columns[k]._symbol_set[1](col)
        return st_copy


def _prepare_manyinsert(pool, partner_store, cols):
    """ Apply column formating to prepare multiple SQL inserts
    Return a copy of partner_store
    """
    values = []
    for partner_val in partner_store:
        values.append(_prepare_insert(pool, partner_val, cols))
    return values


def _insert_partners(cr, pool, partner_store):
    """ Do raw insert into database because ORM is awfully slow
        when doing batch write. It is a shame that batch function
        does not exist"""
    fields = partner_store and partner_store[0].keys() or []
    partner_store = _prepare_manyinsert(pool, partner_store, fields)
    tmp_vals = (', '.join(fields), ', '.join(['%%(%s)s' % i for i in fields]))
    sql = "INSERT INTO res_partner (%s) " \
          "VALUES (%s);" % tmp_vals
    try:
        cr.execute('SAVEPOINT insert_partner')

        cr.executemany(sql, tuple(partner_store))
        # openupgrade.logger.debug('Running %s', sql % tuple(partner_store))
        openupgrade.logger.debug(
            '%s rows inserted into res_partner', cr.rowcount)
        # TODO handle serialized fields
        # sql, tuple(self._serialize_sparse_fields(cols, partner_store)))
    except psycopg2.Error as sql_err:
        cr.execute('ROLLBACK TO SAVEPOINT insert_partner')
        cr.rollback()
        raise osv.except_osv("ORM bypass error", sql_err.pgerror)


def _update_partners(cr, pool, vals):
    """ Do raw update into database because ORM is awfully slow
        when cheking security.
    TODO / WARM: sparse fields are skipped by the method. IOW, if your
    completion rule update an sparse field, the updated value will never
    be stored in the database. It would be safer to call the update method
    from the ORM for records updating this kind of fields.
    """

    fields = vals and vals[0].keys() or []
    vals = _prepare_manyinsert(pool, vals, fields)
    tmp_vals = (', '.join(['%s = %%(%s)s' % (i, i) for i in fields]))
    sql = "UPDATE res_partner " \
          "SET %s where id = %%(id)s;" % tmp_vals
    try:
        cr.execute('SAVEPOINT update_partner')
        not_null_id_vals = [v for v in vals if v['id'] is not False]
        cr.executemany(sql, tuple(not_null_id_vals))
        # openupgrade.logger.debug('Running %s', sql % tuple(partner_store))
        openupgrade.logger.debug(
            '%s rows updated into res_partner', cr.rowcount)
    except psycopg2.Error as sql_err:
        cr.execute('ROLLBACK TO SAVEPOINT update_partner')
        cr.rollback()
        raise osv.except_osv("ORM bypass error", sql_err.pgerror)

# FIXME Migration des correspondances de base_calendar.invite.attendee
# def migrate_contacts(cr, pool):
#     
#     base_calandar_attendee_obj = pool.get('base_calendar.invite.attendee')
#     base_ids = base_calandar_attendee_obj.search(cr, SUPERUSER_ID, [])
#     base_objs = base_calandar_attendee_obj.browse(cr, SUPERUSER_ID, base_ids)
#     for base_obj in base_objs:
#         for contact in base_obj.contact_ids:
#             print("CONTACT .................................... :",contact)

@openupgrade.migrate()
def migrate(cr, version):
    info('# post-migration start (base module)')

    # return  # aborted for testing FIXME MIG

    pool = pooler.get_pool(cr.dbname)
    openupgrade.set_defaults(cr, pool, force_defaults, force=True)
    # circumvent orm when writing to record rules as the orm needs the
    # record rule's model to be instantiatable, which goes wrong at this
    # point for most models
    cr.execute('update ir_rule set active=True')
    migrate_ir_translation(cr)
    migrate_company(cr)
    migrate_partner_address(cr, pool)
    #migrate_base_contact(cr)  # Remplacé par migrate_contact
    migrate_contact(cr, pool)
    update_users_partner(cr, pool)
    reset_currency_companies(cr, pool)
    migrate_res_company_logo(cr, pool)
    openupgrade.load_xml(
        cr, 'base',
        'migrations/7.0.1.3/data.xml')
