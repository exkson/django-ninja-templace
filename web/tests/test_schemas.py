from typing import get_args

from django.test import TestCase

from core.models import OTPChannel, OTPChannelValue


class OTPChannelLiteralDriftTestCase(TestCase):
    """Guard against the model Literal silently drifting from the choices class.

    Every closed-set field gets an ``XChoices`` class (storage contract) and an
    ``X = Literal[...]`` mirror (type contract used by validators and schemas).
    Add one test like this per pair.
    """

    def test_literal_matches_choices(self):
        self.assertEqual(set(get_args(OTPChannelValue)), set(OTPChannel.values))
