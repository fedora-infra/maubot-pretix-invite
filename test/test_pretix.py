import unittest
import json
from event_helper.pretix import Pretix, AttendeeMatrixInformation, question_id_to_header
class TestPretix(unittest.TestCase):

    def test_question_id_to_header(self):
        self.assertEqual(question_id_to_header("matrix"), "Matrix ID")
        # self.assertEqual(question_id_to_header("matrix"), "Matrix ID")

    def test_parse_url(self):
        self.assertEqual(Pretix.parse_invite_url("https://pretix.eu/fedora/matrix-test"), ("fedora", "matrix-test"))


    def test_extract_answers(self):
        response = """
{
	"code": "PNKYZ",
	"event": "matrix-test",
	"status": "p",
	"testmode": false,
	"secret": "vpn4nquljppovsb2",
	"email": "moralcode@fedoraproject.org",
	"phone": null,
	"locale": "en",
	"datetime": "2024-06-06T13:25:30.660168-04:00",
	"expires": "2024-06-20T23:59:59-04:00",
	"payment_date": "2024-06-06",
	"payment_provider": "free",
	"fees": [],
	"total": "0.00",
	"comment": "",
	"custom_followup_at": null,
	"invoice_address": {
		"last_modified": "2024-06-06T13:25:30.683060-04:00",
		"is_business": false,
		"company": "",
		"name": "B",
		"name_parts": {
			"_scheme": "full",
			"full_name": "B"
		},
		"street": "",
		"zipcode": "",
		"city": "",
		"country": "",
		"state": "",
		"vat_id": "",
		"vat_id_validated": false,
		"custom_field": null,
		"internal_reference": ""
	},
	"positions": [
		{
			"id": 28519172,
			"order": "PNKYZ",
			"positionid": 1,
			"item": 548325,
			"variation": null,
			"price": "0.00",
			"attendee_name": null,
			"attendee_name_parts": {},
			"company": null,
			"street": null,
			"zipcode": null,
			"city": null,
			"country": null,
			"state": null,
			"discount": null,
			"attendee_email": null,
			"voucher": null,
			"tax_rate": "0.00",
			"tax_value": "0.00",
			"secret": "a2v8re7fsxxmv2za7mnbnfkqejaapaft",
			"addon_to": null,
			"subevent": null,
			"checkins": [],
			"downloads": [
				{
					"output": "pdf",
					"url": "https://pretix.eu/api/v1/organizers/fedora/events/matrix-test/orderpositions/28519172/download/pdf/"
				},
				{
					"output": "passbook",
					"url": "https://pretix.eu/api/v1/organizers/fedora/events/matrix-test/orderpositions/28519172/download/passbook/"
				}
			],
			"answers": [
				{
					"question": 134081,
					"answer": "@brodie:matrixbots.tinystage.test",
					"question_identifier": "matrix",
					"options": [],
					"option_identifiers": []
				}
			],
			"tax_rule": null,
			"pseudonymization_id": "JPKRXDRSDR",
			"seat": null,
			"canceled": false,
			"valid_from": null,
			"valid_until": null,
			"blocked": null,
			"voucher_budget_use": null
		}
	],
	"downloads": [
		{
			"output": "pdf",
			"url": "https://pretix.eu/api/v1/organizers/fedora/events/matrix-test/orders/PNKYZ/download/pdf/"
		},
		{
			"output": "passbook",
			"url": "https://pretix.eu/api/v1/organizers/fedora/events/matrix-test/orders/PNKYZ/download/passbook/"
		}
	],
	"checkin_attention": false,
	"checkin_text": null,
	"last_modified": "2024-06-06T13:25:30.739512-04:00",
	"payments": [
		{
			"local_id": 1,
			"state": "confirmed",
			"amount": "0.00",
			"created": "2024-06-06T13:25:30.686072-04:00",
			"payment_date": "2024-06-06T13:25:30.722993-04:00",
			"provider": "free",
			"payment_url": null,
			"details": {}
		}
	],
	"refunds": [],
	"require_approval": false,
	"sales_channel": "web",
	"url": "https://pretix.eu/fedora/matrix-test/order/PNKYZ/vpn4nquljppovsb2/",
	"customer": null,
	"valid_if_pending": false
}"""

        resp = json.loads(response)
        print(type(resp))
        print(resp)
        client = Pretix("http://localhost:8000", "1234", "5678", "http://localhost:8000")
        attendee = AttendeeMatrixInformation("PNKYZ", "@brodie:matrixbots.tinystage.test")
        self.assertEqual(client.extract_answers([resp]), [attendee])
if __name__ == '__main__':
    unittest.main()