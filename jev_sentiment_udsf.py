import json
import ssl
import urllib.error
import urllib.request

import vertica_sdk


class jev_sentiment(vertica_sdk.ScalarFunction):
    """UDSF that sends text to the AI gateway and returns the encoded
    sentiment score.

    Inputs (SQL args):
      - state (varchar):        the text to evaluate.
      - instructions (varchar): the evaluation instructions.

    Returns:
      - int: 0 = negative, 1 = positive (encoded label).

    Uses only the Python standard library (urllib + json), so it runs in
    Vertica's minimal Python environment without any third-party packages.
    """

    def setup(self, server_interface, col_types):
        # Read endpoint + API key from UDX parameters (supplied at call time
        # as USING PARAMETERS ...).  See getParameterType() for the
        # parameter declarations.
        params = server_interface.getParamReader()
        self.endpoint = params.getString("endpoint")
        self.api_key = params.getString("api_key")

        # Optional: disable TLS certificate verification (test only).
        verify = True
        if params.containsParameter("verify_ssl"):
            verify = params.getBool("verify_ssl")
        self.ssl_context = None if verify else ssl._create_unverified_context()

    def _score(self, state, instructions):
        """POST to the gateway and return the encoded score (int), or None."""
        payload = json.dumps(
            {
                "model": "typesafe-ai/jev",
                "state": state,
                "questions": {
                    "sentiment": {
                        "type": "score",
                        "instructions": instructions,
                        "criteria": ["negative", "positive"],
                    }
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        score = body["answers"]["sentiment"]["score"]
        # Encoded: 0 = negative, 1 = positive.
        return 1 if score == 1 else 0

    def processBlock(self, server_interface, block_reader, block_writer):
        while True:
            state = block_reader.getString(0)
            instructions = block_reader.getString(1)

            score = None
            try:
                score = self._score(state, instructions)
            except Exception as exc:
                # Log and emit NULL rather than aborting the whole block.
                server_interface.log("ERROR: {}".format(exc))
                score = None

            if score is None:
                block_writer.setNull()
            else:
                block_writer.setInt(score)

            block_writer.next()
            if not block_reader.next():
                break

    def destroy(self, server_interface, col_types):
        pass


class jev_sentiment_factory(vertica_sdk.ScalarFunctionFactory):

    def createScalarFunction(self, srv):
        return jev_sentiment()

    def getPrototype(self, srv_interface, arg_types, return_type):
        # Two varchar inputs: state and instructions.
        arg_types.addVarchar()
        arg_types.addVarchar()
        return_type.addInt()

    def getReturnType(self, srv_interface, arg_types, return_type):
        return_type.addInt()

    def getParameterType(self, srv_interface, parameter_types):
        # Secrets supplied as UDX parameters at call time.
        parameter_types.addVarchar(65000, "endpoint")
        parameter_types.addVarchar(65000, "api_key")
        # Optional test-only flag to skip TLS verification.
        parameter_types.addBool("verify_ssl")
