# Copyright 2021 Studio73 - Ethan Hildick <ethan@studio73.es>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
import logging
import os

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from suds.client import Client
    from suds.sax.text import Raw
    from suds.sudsobject import asdict
except (ImportError, IOError) as err:
    _logger.debug(err)


DACHSER_PRODUCT_CODES = [
    ("1", "EXPRESS"),
    ("2", "EXPRESS CANARIAS"),
    ("3", "EUROEXPRESS"),
    ("4", "PREMIUM HORA LIMITE"),
    ("5", "NIGHT"),
    ("6", "PREMIUM GGSS"),
    ("7", "PREMIUM CANARIAS AEREO"),
    ("8", "EUROEXPRESS PREMIUM"),
    ("9", "SOLUCIONES ESPECIALES"),
    ("10", "CARGO"),
    ("11", "PREMIUM PHARMA"),
    ("12", "PREMIUM LOGÍSTICA"),
    ("13", "FIX"),
    ("14", "10"),
    ("15", "13"),
    ("16", "DOMICILIO"),
    ("20", "LOGISTICA"),
    ("21", "LOGISTICA GAMA BLANCA"),
    ("22", "LOGISTICA 22"),
    ("23", "LOGISTICA 23"),
    ("30", "FTL"),
    ("31", "LTL"),
    ("34", "Targoflex"),
    ("35", "Targospeed"),
    ("36", "Targofix"),
    ("99", "PARCEL"),
]

DACHSER_PORTES = [
    ("P", "Prepaid"),
    ("D", "Due expenses"),
    ("O", "Paid by ordering customer"),
]


class DachserRequest(object):
    """Interface between Dachser API and Odoo recordset
    Abstract Dachser API Operations to connect them with Odoo
    """

    def __init__(self, carrier, request_type):
        endpoint = (
            "https://eview.dachser.com"
            if carrier.prod_environment
            else "https://iberiawebi.dachser.com"
        )
        file_paths = {
            "CrearOrdenRecogidaWS": (
                "/eviewServicios/services/crearOrdenRecogidaWS?wsdl"
            ),
            "ObtenerDetalleExpedicion": (
                "/eviewServicios/services/obtenerDetalleExpedicion?wsdl"
            ),
        }
        self.carrier = carrier
        self.endpoint = "".join([endpoint, file_paths.get(request_type)])
        if carrier.prod_environment:
            request_type += "_Prod"
        wsdl_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "../api",
            request_type + ".wsdl",
        )
        # All requests use INTEROPERABILIDAD/INTEROPERABILIDAD HTTP credentials
        self.client = Client(
            "file:{}".format(wsdl_path),
            headers={
                "Authorization": (
                    "Basic SU5URVJPUEVSQUJJTElEQUQ6SU5URVJPUEVSQUJJTElEQUQ="
                )
            },
        )

    def _recursive_asdict(self, suds_object):
        """As suds response is an special object, we convert it into
        a more usable python dict. Taken form:
        https://stackoverflow.com/a/15678861
        """
        out = {}
        for k, v in asdict(suds_object).items():
            if hasattr(v, "__keylist__"):
                out[k] = self._recursive_asdict(v)
            elif isinstance(v, list):
                out[k] = []
                for item in v:
                    if hasattr(item, "__keylist__"):
                        out[k].append(self._recursive_asdict(item))
                    else:
                        out[k].append(item)
            else:
                out[k] = v
        return out

    def _handle_error(self, result):
        error_code = int(result["codigoResultado"])
        if error_code < 0:
            raise UserError(
                _(
                    "DACHSER returned an error trying to record the shipping.\n"
                    "Error:\n{}: {}"
                ).format(error_code, result["descripcionResultado"])
            )

    def _prepare_shipping(self, vals):
        xml = """
            <cre:arg1>
                <cre:DatosCrearOrdenRecogidaWS>
                    {cod_cliente_ord_xml}
                    {postal_con_xml}
                    {postal_rem_xml}
                    {portes_xml}
                    {contact_ord_xml}
                    {street_con_xml}
                    {street2_con_xml}
                    {street_rem_xml}
                    {street2_rem_xml}
                    {email_con_xml}
                    {email_rem_xml}
                    {fecha_entrega_xml}
                    {nif_con_xml}
                    {nif_rem_xml}
                    {name_con_xml}
                    {name_rem_xml}
                    {packages_xml}
                    {notes_xml}
                    {country_con_xml}
                    {country_rem_xml}
                    {password_xml}
                    {weight_xml}
                    {city_con_xml}
                    {city_rem_xml}
                    {product_xml}
                    {customer_ref_xml}
                    {tel_con_xml}
                    {tel_ord_xml}
                    {tel_rem_xml}
                    {username_xml}
                </cre:DatosCrearOrdenRecogidaWS>
            </cre:arg1>
        """
        vals.update(
            {
                "cod_cliente_ord_xml": (
                    """<codClienteOrdenante>{cod_cliente_ord}</codClienteOrdenante>
                    """.format(
                        cod_cliente_ord=vals.get("cod_cliente_ord")
                    )
                ),
                "postal_con_xml": (
                    """<codPostalConsignatario>{postal_con}</codPostalConsignatario>
                    """.format(
                        postal_con=vals.get("postal_con")
                    )
                ),
                "postal_rem_xml": (
                    "<codPostalRemitente>{postal_rem}</codPostalRemitente>".format(
                        postal_rem=vals.get("postal_rem")
                    )
                ),
                "portes_xml": (
                    "<codTipoPorte>{portes}</codTipoPorte>".format(
                        portes=vals.get("portes")
                    )
                ),
                "contact_ord_xml": (
                    "<contactoOrdenante>{contact_ord}</contactoOrdenante>".format(
                        contact_ord=vals.get("contact_ord")
                    )
                ),
                "street_con_xml": (
                    """<direccionConsignatario>{street_con}</direccionConsignatario>
                    """.format(
                        street_con=vals.get("street_con")
                    )
                ),
                "street2_con_xml": (
                    """<direccionConsignatario2>{street2_con}</direccionConsignatario2>
                    """.format(
                        street2_con=vals.get("street2_con")
                    )
                    if vals.get("street2_con", False)
                    else ""
                ),
                "street_rem_xml": (
                    "<direccionRemitente>{street_rem}</direccionRemitente>".format(
                        street_rem=vals.get("street_rem")
                    )
                ),
                "street2_rem_xml": (
                    "<direccionRemitente2>{street2_rem}</direccionRemitente2>".format(
                        street2_rem=vals.get("street2_rem")
                    )
                    if vals.get("street2_rem", False)
                    else ""
                ),
                "email_con_xml": (
                    "<emailConsignatario>{email_con}</emailConsignatario>".format(
                        email_con=vals.get("email_con")
                    )
                    if vals.get("email_con", False)
                    else ""
                ),
                "email_rem_xml": (
                    "<emailRemitente>{email_rem}</emailRemitente>".format(
                        email_rem=vals.get("email_rem")
                    )
                    if vals.get("email_rem", False)
                    else ""
                ),
                "fecha_entrega_xml": (
                    "<fechaEntrega>{fecha_entrega}</fechaEntrega>".format(
                        fecha_entrega=vals.get("fecha_entrega")
                    )
                ),
                "nif_con_xml": (
                    "<nifConsignatario>{nif_con}</nifConsignatario>".format(
                        nif_con=vals.get("nif_con")
                    )
                    if vals.get("nif_con", False)
                    else ""
                ),
                "nif_rem_xml": (
                    "<nifRemitente>{nif_rem}</nifRemitente>".format(
                        nif_rem=vals.get("nif_rem")
                    )
                    if vals.get("nif_rem", False)
                    else ""
                ),
                "name_con_xml": (
                    "<nombreConsignatario>{name_con}</nombreConsignatario>".format(
                        name_con=vals.get("name_con")
                    )
                ),
                "name_rem_xml": (
                    "<nombreRemitente>{name_rem}</nombreRemitente>".format(
                        name_rem=vals.get("name_rem")
                    )
                ),
                "packages_xml": (
                    "<numBultos>{packages}</numBultos>".format(
                        packages=vals.get("packages")
                    )
                ),
                "notes_xml": (
                    "<observaciones>{notes}</observaciones>".format(
                        notes=vals.get("notes")
                    )
                    if vals.get("notes", False)
                    else ""
                ),
                "country_con_xml": (
                    "<paisConsignatario>{country_con}</paisConsignatario>".format(
                        country_con=vals.get("country_con")
                    )
                ),
                "country_rem_xml": (
                    "<paisRemitente>{country_rem}</paisRemitente>".format(
                        country_rem=vals.get("country_rem")
                    )
                ),
                "password_xml": (
                    "<password>{password}</password>".format(
                        password=vals.get("password")
                    )
                ),
                "weight_xml": (
                    "<peso>{weight}</peso>".format(weight=vals.get("weight"))
                ),
                "city_con_xml": (
                    """<poblacionConsignatario>{city_con}</poblacionConsignatario>
                    """.format(
                        city_con=vals.get("city_con")
                    )
                ),
                "city_rem_xml": (
                    "<poblacionRemitente>{city_rem}</poblacionRemitente>".format(
                        city_rem=vals.get("city_rem")
                    )
                ),
                "product_xml": (
                    "<producto>{product}</producto>".format(product=vals.get("product"))
                ),
                "customer_ref_xml": (
                    "<referenciaCliente2>{customer_ref}</referenciaCliente2>".format(
                        customer_ref=vals.get("customer_ref")
                    )
                    if vals.get("customer_ref", False)
                    else ""
                ),
                "tel_con_xml": (
                    "<telfConsignatario>{tel_con}</telfConsignatario>".format(
                        tel_con=vals.get("tel_con")
                    )
                    if vals.get("tel_con", False)
                    else ""
                ),
                "tel_ord_xml": (
                    "<telfOrdenante>{tel_ord}</telfOrdenante>".format(
                        tel_ord=vals.get("tel_ord")
                    )
                ),
                "tel_rem_xml": (
                    "<telfRemitente>{tel_rem}</telfRemitente>".format(
                        tel_rem=vals.get("tel_rem")
                    )
                ),
                "username_xml": (
                    "<usuario>{username}</usuario>".format(
                        username=vals.get("username")
                    )
                ),
            }
        )
        return xml.format(**vals)

    def _send_shipping(self, vals):
        """Create new shipment
        :params vals dict of needed values
        :returns dict with Dachser response containing the booking ID and label
        """
        xml = Raw(self._prepare_shipping(vals))
        _logger.debug(xml)
        try:
            res = self.client.service.crearOrdenRecogidaWS(xml)
        except Exception as e:
            raise UserError(
                _(
                    "No response from server recording Dachser delivery.\n"
                    "Traceback:\n{}"
                ).format(e)
            )
        # Convert result suds object to dict
        res = self._recursive_asdict(res)
        _logger.debug(res)
        self._handle_error(res)
        return res

    def _prepare_tracking_link(self, vals):
        xml = """
            <arg1>
                {postal_dest_xml}
                {barcode_xml}
                {locator_hash_xml}
                {customer_ref_xml}
                {dachser_ref_xml}
                {password_xml}
                {username_xml}
            </arg1>
        """
        vals.update(
            {
                "postal_dest_xml": (
                    """<codPostalDestinatario>{postal_dest}</codPostalDestinatario>
                    """.format(
                        postal_dest=vals.get("postal_dest")
                    )
                    if vals.get("postal_dest", False)
                    else ""
                ),
                "barcode_xml": (
                    """<codigoEtiqueta>{barcode}</codigoEtiqueta>""".format(
                        barcode=vals.get("barcode")
                    )
                    if vals.get("barcode", False)
                    else ""
                ),
                "locator_hash_xml": (
                    """<localizador>{locator_hash}</localizador>""".format(
                        locator_hash=vals.get("locator_hash")
                    )
                    if vals.get("locator_hash", False)
                    else ""
                ),
                "customer_ref_xml": (
                    """<numReferencia>{customer_ref}</numReferencia>""".format(
                        customer_ref=vals.get("customer_ref")
                    )
                    if vals.get("customer_ref", False)
                    else ""
                ),
                "dachser_ref_xml": (
                    """<numUnico>{dachser_ref}</numUnico>""".format(
                        dachser_ref=vals.get("dachser_ref")
                    )
                    if vals.get("dachser_ref", False)
                    else ""
                ),
                "password_xml": (
                    """<password>{password}</password>""".format(
                        password=vals.get("password")
                    )
                ),
                "username_xml": (
                    """<userAzkarview>{username}</userAzkarview>""".format(
                        username=vals.get("username")
                    )
                ),
            }
        )
        return xml.format(**vals)

    def _get_tracking_link(self, vals):
        xml = Raw(self._prepare_tracking_link(vals))
        _logger.debug(xml)
        try:
            res = self.client.service.obtenerURL(xml)
        except Exception as e:
            raise UserError(
                _(
                    "No response from server recording Dachser delivery.\n"
                    "Traceback:\n{}"
                ).format(e)
            )
        # Convert result suds object to dict
        res = self._recursive_asdict(res)
        _logger.debug(res)
        self._handle_error(res)
        return res

    def _prepare_tracking_state(self, vals):
        xml = """
            <arg1>
                {codBideaDelegacionDestino_xml}
                {codBideaDelegacionOrigen_xml}
                {codigoBarras_xml}
                {expedicion_xml}
                {fechaExpedicion_xml}
                {numRecogida_xml}
                {numReferencia_xml}
                {numUnico_xml}
                {password_xml}
                {sscc_xml}
                {username_xml}
            </arg1>
        """
        vals.update(
            {
                "codBideaDelegacionDestino_xml": (
                    """<codBideaDelegacionDestino>{}</codBideaDelegacionDestino>
                    """.format(
                        vals.get("dest_depot")
                    )
                    if vals.get("dest_depot", False)
                    else ""
                ),
                "codBideaDelegacionOrigen_xml": (
                    """<codBideaDelegacionOrigen>{}</codBideaDelegacionOrigen>
                    """.format(
                        vals.get("origin_depot")
                    )
                    if vals.get("origin_depot", False)
                    else ""
                ),
                "codigoBarras_xml": (
                    """<codigoBarras>{barcode}</codigoBarras>""".format(
                        barcode=vals.get("barcode")
                    )
                    if vals.get("barcode", False)
                    else ""
                ),
                "expedicion_xml": (
                    """<expedicion>{expedicion}</expedicion>""".format(
                        expedicion=vals.get("expedicion")
                    )
                    if vals.get("expedicion", False)
                    else ""
                ),
                "fechaExpedicion_xml": (
                    """<fechaExpedicion>{fecha_expedicion}</fechaExpedicion>""".format(
                        fecha_expedicion=vals.get("fecha_expedicion")
                    )
                    if vals.get("fecha_expedicion", False)
                    else ""
                ),
                "numRecogida_xml": (
                    """<numRecogida>{num_recogida}</numRecogida>""".format(
                        num_recogida=vals.get("num_recogida")
                    )
                    if vals.get("num_recogida", False)
                    else ""
                ),
                "numReferencia_xml": (
                    """<numReferencia>{num_referencia}</numReferencia>""".format(
                        num_referencia=vals.get("num_referencia")
                    )
                    if vals.get("num_referencia", False)
                    else ""
                ),
                "numUnico_xml": (
                    """<numUnico>{num_unico}</numUnico>""".format(
                        num_unico=vals.get("num_unico")
                    )
                    if vals.get("num_unico", False)
                    else ""
                ),
                "password_xml": (
                    """<password>{password}</password>""".format(
                        password=vals.get("password")
                    )
                ),
                "sscc_xml": (
                    """<sscc>{sscc}</sscc>""".format(sscc=vals.get("sscc"))
                    if vals.get("sscc", False)
                    else ""
                ),
                "username_xml": (
                    """<userAzkarview>{username}</userAzkarview>""".format(
                        username=vals.get("username")
                    )
                ),
            }
        )
        return xml.format(**vals)

    def _get_tracking_state(self, vals):
        xml = Raw(self._prepare_tracking_state(vals))
        _logger.debug(xml)
        try:
            res = self.client.service.obtenerDetalleExpedicion(xml)
        except Exception as e:
            raise UserError(
                _(
                    "No response from server recording Dachser delivery.\n"
                    "Traceback:\n{}"
                ).format(e)
            )
        # Convert result suds object to dict
        res = self._recursive_asdict(res)
        _logger.debug(res)
        self._handle_error(res)
        return res
