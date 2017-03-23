# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2015 Therp BV (<http://therp.nl>).
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
import pooler

from openerp.openupgrade import openupgrade


@openupgrade.migrate()
def migrate(cr, version):
    """Compute procurement.order's sale_line_id
    then project.task's sale_line_id.
    """
    cr.execute("""
        update procurement_order
        set sale_line_id = so.id
        from sale_order_line so
        where so.procurement_id = procurement_order.id
    """)
    cr.execute("""
        update project_task pt
        set sale_line_id = po.sale_line_id
        from procurement_order po
        where po.id = pt.procurement_id
        and po.sale_line_id is not null
    """)