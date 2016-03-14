import base64
import hashlib
import hmac
import markdown
import random
import re
import requests
import xmltodict

from errbot import BotPlugin, re_botcmd


def escape(text):
    """Escape some Markdown text"""
    for char in '*_`[]':
        text = text.replace(char, '\\'+char)
    return text


class Kayako(BotPlugin):
    """
    A plugin to interface with Kayako helpdesk
    """
    def _generate_signature(self):
        """Generate a signature for a Kayako API call"""
        salt = str(random.getrandbits(16)).encode('utf-8')
        encrypted_signature = hmac.new(
                self.config['SECRET_KEY'].encode('utf-8'),
                msg=salt,
                digestmod=hashlib.sha256
        ).digest()
        return salt, base64.b64encode(encrypted_signature)


    def _api_call(self, endpoint, params=None):
        """Make an API call to the Kayako REST API"""
        if params is None:
            params = {}

        salt, signature = self._generate_signature()
        params.update({
            'e': endpoint,
            'apikey': self.config['API_KEY'],
            'salt': salt,
            'signature': signature,
        })

        url = "{base}/api/index.php".format(base=self.config['BASE_URL'])
        r = requests.get(url, params=params)
        r.raise_for_status()
        return xmltodict.parse(r.text)


    def activate(self):
        """
        Triggers on plugin activation

        You should delete it if you're not using it to override any default behaviour
        """
        random.seed()
        super(Kayako, self).activate()

    def get_configuration_template(self):
        """
        Defines the configuration structure this plugin supports

        You should delete it if your plugin doesn't use any configuration like this
        """
        return {'API_KEY': "",
                'SECRET_KEY': "",
                'BASE_URL': "https://",
               }

    def check_configuration(self, configuration):
        """
        Triggers when the configuration is checked, shortly before activation

        You should delete it if you're not using it to override any default behaviour
        """
        super(Kayako, self).check_configuration(configuration)

    @re_botcmd(pattern=r"(^| )kayako( ticket)? #?(?P<ticketid>(([A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{5})|[0-9]+))", prefixed=False, flags=re.IGNORECASE, template="ticketsummary")
    def watch_for_ticket_mentions(self, msg, match):
        """
        Watch for messages containing a Kayako ticket ID and print a
        short summary into the chat if any are seen.
        """
        displayid = match.groupdict()['ticketid']
        self.log.info("Looking up details for ticket '%s'", displayid)
        try:
            reponse = self._api_call('/Tickets/Ticket/%s' % displayid)
            ticket = reponse['tickets']['ticket']
            return {
                'ticketid': ticket['@id'],
                'displayid': displayid,
                'summary': escape(ticket['subject']),
                'base_url': self.config['BASE_URL'],
            }
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.log.info("Ticket '%s' doesn't exist.", displayid)
            else:
                self.log.exception("An HTTP error occurred while trying to look up ticket '%s'", displayid)
        except Exception as e:
            self.log.exception("An error occurred while trying to look up ticket '%s'", displayid)
