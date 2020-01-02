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
import sys

def info(*msgs):
    for msg in msgs:
        print(msg)
    sys.stdout.flush()

def pgstr(val):
    return "'" + val.replace("'", "''") + "'"


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
    cr.execute(
        "ALTER TABLE res_partner "
        "ADD column openupgrade_7_migrated_from_user_id "
        " INTEGER")

    fields = ['id', 'function', 'sequence_partner', 'address_id', 'fax', 'extension', 'sequence_contact', 'date_start', 'date_stop',
              'contact_id', 'phone', 'state', 'other', 'email', 'id_sfl', 'id_adherent', 'mobile', 'default_ok', 'actif_ok', 'active',
              'fax_e164', 'mobile_e164', 'phone_e164', 'count_phone_dials']

    cr.execute(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_name = 'res_partner';")
    partner_fields = [i[0] for i in cr.fetchall()]

    # A cette étape les addresses sont déjà migrées
    addresses_with_contact = []  # ids res.partner

    # GET FIELDS
    def _get_contact_fields(fields_list):
        cr.execute(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_name = 'res_partner_contact';")
        available_fields = set(i[0] for i in cr.fetchall())
        info('## champs ignorés dans res_partner_contact ##', available_fields - set(fields_list))
        # keep fields that are found in res_partner // to avoid crash
        return available_fields.intersection(fields_list)
    fields_contact = _get_contact_fields(partner_fields)
    info('## contact fields ##', fields_contact)

    def _get_address_fields(fields_list):
        cr.execute(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_name = 'res_partner_address';")
        available_fields = set(i[0] for i in cr.fetchall())
        info('## champs ignorés dans res_partner_address ##', available_fields - set(fields_list))
        # keep fields that are found in res_partner // to avoid crash
        return available_fields.intersection(fields_list)
    fields_address = _get_address_fields(partner_fields)
    info('## address fields ##',fields_address)

    def _fetch_rows(table, columns, whereclause=None):
        # recupere les colonnes de la table specifie
        cr.execute(
            "SELECT " + ', '.join(columns) + "\n"
            "FROM %s\n"
            "%s" % (table,
                    ('WHERE ' + whereclause) if whereclause else ''))

        for row in cr.fetchall():
            # yield permet de retourner les valeurs ligne par ligne
            yield dict(zip(columns,
                                   [val or False for val in row]
                                   ))

    def _fetch_row(*args,**kargs):
        for row in _fetch_rows(*args,**kargs):
            return row

    def _fetch_val(table, column, whereclause):
        cr.execute(
            "SELECT %s FROM %s WHERE %s" % (
                column, table, whereclause))
        return cr.fetchone()[0]

    # PARTNER (contact) CREATION functions
    def _set_contact_partner(contact_id, partner_id, user_id=False):
        cr.execute(
            "UPDATE res_partner_contact "
            "SET openupgrade_7_migrated_to_partner_id = %s "
            "WHERE id = %s" %
            (partner_id, contact_id))
        cr.execute(
          "UPDATE res_partner "
          "SET openupgrade_7_migrated_from_contact_id = %s, "
          "    openupgrade_7_migrated_from_user_id = %s "
          "WHERE id = %s" %
          (contact_id, user_id or 'null', partner_id))
        contact_partner_hash[contact_id] = partner_id

    def _create_partner_contact(contact_id, vals,
                        partner_address_id=False,
                        job_id=False,
                        function='', partner_contact_id=False):
        """
        Create a partner from a contact. Update the vals
        with the defaults only if the keys do not occur
        already in vals. Register the created partner_id
        on the obsolete contact table
        """
        contact_id_bis = vals.pop('id')
        if not partner_contact_id:
            vals['contact_type'] = 'standalone'
            #Cas où le contact n'a pas encore été créé, alors on en crée un ....
            if not vals['name']:
                vals['name'] = ''
            partner_id = partner_obj.create(cr, SUPERUSER_ID, vals)

            partner_contact_id = int(partner_id)
            _set_contact_partner(contact_id, partner_contact_id)
        else:
            #Sinon on prend le nouvel id correspond au contact
            if partners_to_update.get(partner_contact_id, False):
                #maj des infos
                vals['contact_type'] = 'standalone'
                query_set_fields = ",".join(
                    [ u"%s=%s" % (
                        k,
                        (isinstance(v, str) or isinstance(v, unicode))
                        and pgstr(v) or
                        isinstance(v, bool) and ('true' if v else 'false')
                        or str(v))
                     for k,v in vals.iteritems() if v])
                cr.execute(u"UPDATE res_partner SET %s WHERE id=%s " % (
                    query_set_fields, partner_contact_id))
                partners_to_update.pop(partner_contact_id)
        vals['id'] = contact_id_bis


        # partner_obj.write(cr, SUPERUSER_ID, [partner_contact_id], {
        #     'parent_id': parent_id})
        # set_address_partner(address_id, partner_contact_id)

        #print("PARTNER ID :", partner_contact_id)
        if partner_address_id:
            #partner_obj.write(cr, SUPERUSER_ID, [partner_contact_id], {'contact_type': 'attached'})
            cr.execute("UPDATE res_partner "
                       "SET contact_type='attached' "
                       "WHERE id=%s" % (partner_contact_id,))

            query_set_fields =  u"contact_id=%s" % partner_contact_id
            query_set_fields +=  u", function=%s" % pgstr(function)
            query_set_fields += (
                u", openupgrade_7_migrated_from_job_id=%s" % job_id)
            if partner_address_id in addresses_with_contact:
                #Cas où le RPA est déjà lié à un contact
                #On charge les valeurs du RPA déjà lié pour encréer un nouveau afin de le lier au contact
                address_vals = _load_address_vals(
                    partner_address_id,
                    partner_fields +
                    ['openupgrade_7_migrated_from_address_id'])
                query_set_fields += (
                    u", openupgrade_7_migrated_from_address_id=%s" %
                    address_vals['openupgrade_7_migrated_from_address_id']
                )
                address_vals['contact_id'] = partner_contact_id
                if not address_vals['name']:
                    address_vals['name'] = ''
                partner_address_id = partner_obj.create(cr, SUPERUSER_ID, address_vals)

                # Pour le cas courant et
                # le cas où le RPA n'est lié à aucun contact
                # la suite est identique
            cr.execute(u"UPDATE res_partner SET %s WHERE id=%s " % (
                query_set_fields, partner_address_id))
            # other_contact_ids est un One2many, donc il y a un Many2one
            # correspondant res.partner/contact_id (déjà géré)
            addresses_with_contact.append(partner_address_id)
        return partner_contact_id

    # GETTER FOR VALS AND NEW PARTNERS
    def _load_contact_vals(contact_id, columns):
        return _fetch_row('res_partner_contact', columns,
                          'id = %s' % contact_id)

    def _load_address_vals(address_id, columns):
        return _fetch_row('res_partner', columns,
                          'id = %s' % address_id)

    address_partner_hash = {}  # cache for rpa -> rp
    def _get_address_partner_id(old_address_id):
        new_id = address_partner_hash.get(old_address_id, False)
        if not new_id:
            new_id = _fetch_val('res_partner_address',
                                'openupgrade_7_migrated_to_partner_id',
                                'id = %s' % old_address_id)
            address_partner_hash[old_address_id] = new_id
        return new_id

    contact_partner_hash = {}  # cache for rpc -> rp
    partners_to_update = {}

    cr.execute(
        "select rpc.id, rpc.user_id, ru.openupgrade_7_created_partner_id "
        "from res_partner_contact rpc "
        "left outer join res_users ru on rpc.user_id = ru.id "
        "where rpc.user_id is not null;");

    for row in cr.fetchall():
        old_contact_id, user_id, new_id = row
        _set_contact_partner(old_contact_id, new_id, user_id)
        partners_to_update[new_id] = True

    def _get_contact_user_id(old_contact_id, default=False):
         return contact_user_hash.get(old_contact_id, default)

    def _get_contact_partner_id(old_contact_id):
        new_id = contact_partner_hash.get(old_contact_id, False)
        if not new_id:
            new_id = _fetch_val('res_partner_contact',
                                'openupgrade_7_migrated_to_partner_id',
                                'id = %s' % old_contact_id)
            contact_partner_hash[old_contact_id] = new_id
        return new_id


    # MAIN PART
    def _proccess_all_contacts():
        # fetch all partner_job
        for dict_values in _fetch_rows(
                'res_partner_job',
                fields,
                'id is not null'):
            # default
            contact_vals = {}
            partner_address_id = False

            if dict_values['address_id'] != False:
                partner_address_id = _get_address_partner_id(dict_values['address_id'])
            if dict_values['contact_id'] != False:
                contact_vals = _load_contact_vals(dict_values['contact_id'], fields_contact)
                _create_partner_contact(
                    dict_values['contact_id'],
                    contact_vals,
                    partner_address_id=partner_address_id,
                    function=dict_values['function'],
                    job_id=dict_values['id'],
                    partner_contact_id=_get_contact_partner_id(dict_values['contact_id'])
                )


        # (Prévu por le reste des contacts non migrés)
        for dict_values in _fetch_rows(
                'res_partner_contact',
                fields_contact,
                'openupgrade_7_migrated_to_partner_id IS null'):
            if not dict_values['id'] in contact_partner_hash:
                _create_partner_contact(
                    dict_values['id'],
                    dict_values)

    _proccess_all_contacts()


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
        "ALTER TABLE res_partner "
        "ADD column openupgrade_7_migrated_from_job_id "
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

        # FIXME : managed by create_partner_w_addr (to add parent_id)
        # _insert_partners(cr, pool, partner_store_insert)
        # _update_partners(cr, pool, partner_store_update)

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
    process_address_type(cr, pool, fields.copy(), "type = 'default'")

    # then try the ones without type and without name
    process_address_type(
        cr, pool, fields.copy(),
        "(type IS NULL OR type = '') AND (name IS NULL OR name = '')")
    # and only then just without type
    process_address_type(
        cr, pool, fields.copy(),
        "(type IS NULL OR type = '') AND name <> ''")
    # Not in clause is very slow. we replace them by an ubptade on a new column
    set_address_processed(processed_ids)
    process_address_type(
        cr, pool, fields.copy(),
        "openupgrade_7_address_processed IS NULL ")
    # set_address_processed(processed_ids)

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
