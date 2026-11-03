# Mistral Provider Configuration

A valid mistral configuration is a json object with the following fields:

| Name                      | Type      | Optional                 | Description                                                                                             |
| ------------------------- | --------- | ------------------------ | ------------------------------------------------------------------------------------------------------- |
| type                      | "mistral" | no                       | Identifying the provider as a mistral configuration                                                     |
| api_key                   | str       | no                       | The api key for mistral. This can also be an environment variable by specifying it as "ENV:\<var-name>" |
| enable_framework_messages | boolean   | yes (default is "False") | Enable the translation of framework messages which are not natively supported by mistral                |
| models                    | list[str] | no                       | If set, only these model ids are allowed to be used                                                     |
