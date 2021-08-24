# Copyright 2021 Studio73 - Ethan Hildick <ethan@studio73.es>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


from odoo import _, fields, models

from .dachser_request import DACHSER_PORTES, DACHSER_PRODUCT_CODES, DachserRequest


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("dachser", "DACHSER")], ondelete={"dachser": "set default"}
    )
    dachser_user = fields.Char(
        string="Username", help="eView username provided by DACHSER Spain"
    )
    dachser_password = fields.Char(
        string="Password", help="eView password for userAzkarview"
    )
    dachser_code = fields.Char(
        string="Código cliente", help="DACHSER Ordering customer code"
    )
    dachser_product_code = fields.Selection(
        string="Código de producto", selection=DACHSER_PRODUCT_CODES
    )
    dachser_expenses = fields.Selection(
        string="Type of expenses", selection=DACHSER_PORTES
    )

    def _prepare_validation_vals(self):
        return {
            "username": self.dachser_user,  # Mandatory
            "password": self.dachser_password,  # Mandatory
        }

    def _prepare_shipper_vals(self, picking):
        shipper = (
            picking.picking_type_id.warehouse_id.partner_id
            or picking.company_id.partner_id
        )
        return {
            "postal_rem": (shipper.zip or shipper.parent_id.zip or ""),  # Mandatory
            "street_rem": (
                shipper.street or shipper.parent_id.street or ""
            ),  # Mandatory
            "street2_rem": shipper.street2 or shipper.parent_id.street2 or "",
            "email_rem": shipper.email or shipper.parent_id.email or "",
            "nif_rem": "",
            "name_rem": shipper.name or shipper.parent_id.name or "",  # Mandatory
            "country_rem": (
                shipper.country_id.code or shipper.parent_id.country_id.code
            ),  # Mandatory
            "city_rem": shipper.city or shipper.parent_id.city or "",  # Mandatory
            "tel_rem": shipper.phone or shipper.parent_id.phone or "",
        }

    def _prepare_consignee_vals(self, picking):
        consignee = picking.partner_id
        return {
            "postal_con": (consignee.zip or consignee.parent_id.zip or ""),  # Mandatory
            "street_con": (
                consignee.street or consignee.parent_id.street or ""
            ),  # Mandatory
            "street2_con": consignee.street2 or consignee.parent_id.street2 or "",
            "email_con": consignee.email or consignee.parent_id.email or "",
            "nif_con": "",
            "name_con": consignee.name or consignee.parent_id.name or "",  # Mandatory
            "country_con": (
                consignee.country_id.code or consignee.parent_id.country_id.code
            ),  # Mandatory
            "city_con": consignee.city or consignee.parent_id.city or "",  # Mandatory
            "tel_con": consignee.phone or consignee.parent_id.phone or "",
        }

    def _prepare_booking_vals(self, picking):
        shipper = (
            picking.picking_type_id.warehouse_id.partner_id
            or picking.company_id.partner_id
        )
        return dict(
            {
                "cod_cliente_ord": self.dachser_code,  # Mandatory
                "contact_ord": self.dachser_code,  # Mandatory
                "tel_ord": (
                    shipper.phone or shipper.parent_id.phone or ""
                ),  # Mandatory
                "portes": self.dachser_expenses,  # Mandatory
                "notes": picking.note or "",
                "fecha_entrega": (
                    "" if self.dachser_product_code != "13" else picking.scheduled_date
                ),  # Mandatory IF Product = "13-FIX"
                "weight": picking.shipping_weight,  # Mandatory
                "product": self.dachser_product_code,  # Mandatory
                "customer_ref": picking.name,
                "packages": picking.number_of_packages,
            },
            **self._prepare_validation_vals(),
            **self._prepare_shipper_vals(picking),
            **self._prepare_consignee_vals(picking),
        )

    def dachser_send_shipping(self, pickings):
        """Send the package to DACHSER
        :param pickings: A recordset of pickings
        :return list: A list of dictionaries although in practice it's
        called one by one and only the first item in the dict is taken. Due
        to this design, we have to inject vals in the context to be able to
        add them to the message.
        """
        request = DachserRequest(self, "CrearOrdenRecogidaWS")
        result = []
        for picking in pickings:
            vals = self._prepare_booking_vals(picking)
            response = request._send_shipping(vals)
            if not response or response.get("_return", -1) < 0:
                result.append(vals)
                continue
            vals["tracking_number"] = response.get("numeroOrdenRecogida", "")
            # We post an extra message in the chatter with the rest of the response
            body = _(
                "DACHSER Shipping extra info:\n"
                "Reference: {}, Pickup no.: {}, Request list position: {}"
            ).format(
                response.get("referencia", "N/A"),
                response.get("numeroOrdenRecogida", "N/A"),
                response.get("numeroPeticion", "N/A"),
            )
            picking.message_post(body=body)
            result.append(vals)
        return result

    def _prepare_tracking_link_vals(self, picking):
        return dict(
            {
                "customer_ref": picking.name,
                "dachser_code": "",
                "locator_hash": "",
                "barcode": "",
                "postal_dest": "",
            },
            **self._prepare_validation_vals(),
        )

    def dachser_get_tracking_link(self, picking):
        """Provide tracking link for the customer"""
        self.ensure_one()
        request = DachserRequest(self, "ObtenerDetalleExpedicion")
        vals = self._prepare_tracking_link_vals(picking)
        response = request._get_tracking_link(vals)
        return response.get("descripcionResultado", "")

    def _prepare_tracking_state_vals(self, picking):
        return dict(
            {
                "dest_depot": "",
                "origin_depot": "",
                "barcode": "",
                "expedicion": "",
                "fecha_expedicion": "",
                "num_recogida": picking.carrier_tracking_ref,
                "num_referencia": "",
                "num_unico": "",
                "sscc": "",
            },
            **self._prepare_validation_vals(),
        )

    def dachser_tracking_state_update(self, picking):
        """Tracking state update"""
        self.ensure_one()
        if not picking.carrier_tracking_ref:
            return
        request = DachserRequest(self, "ObtenerDetalleExpedicion")
        vals = self._prepare_tracking_state_vals(picking)
        response = request._get_tracking_state(vals)
        picking.write(
            {
                "date_delivered": response.get("fechaEntrega"),
                "tracking_state": response.get("estado"),
                "tracking_state_history": "\n".join(
                    [
                        (
                            "{} - {}".format(
                                picking.date_delivered, picking.tracking_state
                            )
                            if picking.date_delivered and picking.tracking_state
                            else ""
                        ),
                        "{} - {}".format(
                            response.get("fechaEntrega"), response.get("estado")
                        ),
                    ]
                ),
            }
        )

    def dachser_cancel_shipment(self, pickings):
        """Cancel the expedition"""
        raise NotImplementedError(
            _(
                """
                DACHSER does not currently support cancelling shipments
                through webservice
            """
            )
        )

    def dachser_rate_shipment(self, order):
        """Not implemented"""
        raise NotImplementedError(
            _(
                """
                DACHSER API doesn't provide methods to compute delivery rates, so
                you should rely on another price method instead or override this
                one in your custom code.
            """
            )
        )
