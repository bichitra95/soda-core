from json import dumps

from pyatlan.errors import AtlanError

from soda.contracts.contract import ContractResult
from soda.contracts.impl.logs import Logs
from soda.contracts.impl.plugin import Plugin
from soda.contracts.impl.yaml_helper import YamlFile


class AtlanPlugin(Plugin):

    def __init__(self, logs: Logs, plugin_name: str, plugin_yaml_files: list[YamlFile]):
        super().__init__(logs, plugin_name, plugin_yaml_files)
        atlan_configuration_dict: dict = self.plugin_yaml_files[0].dict
        self.atlan_api_key: str = atlan_configuration_dict["atlan_api_key"]
        self.atlan_base_url: str = atlan_configuration_dict["atlan_base_url"]

    def process_contract_results(self, contract_result: ContractResult) -> None:
        error_messages: list[str] = []
        atlan_qualified_name: str = contract_result.data_source_yaml_dict.get("atlan_qualified_name")
        if not isinstance(atlan_qualified_name, str):
            error_messages.append("atlan_qualified_name is required in a data source configuration yaml")

        database_name: str = contract_result.contract.database_name
        if not isinstance(database_name, str):
            error_messages.append("database is required in the contract yaml")

        schema_name: str = contract_result.contract.schema_name
        if not isinstance(schema_name, str):
            error_messages.append("schema is required in the contract yaml")

        dataset_name: str = contract_result.contract.dataset_name
        dataset_atlan_qualified_name: str = f"{atlan_qualified_name}/{database_name}/{schema_name}/{dataset_name}"

        if error_messages:
            error_messages_text = ", ".join(error_messages)
            self.logs.error(
                f"Atlan integration cannot be activated as not all "
                f"integration requirements are met: {error_messages_text}"
            )
            return None

        contract_dict: dict = contract_result.contract.contract_file.dict.copy()
        contract_dict.setdefault("kind", "DataContract")

        contract_json_str: str = dumps(contract_dict)

        self.logs.info(f"Pushing contract to Atlan: {dataset_atlan_qualified_name}")

        from pyatlan.client.atlan import AtlanClient
        from pyatlan.model.assets import DataContract

        client = AtlanClient(base_url=self.atlan_base_url, api_key=self.atlan_api_key)
        contract = DataContract.creator(  #
            asset_qualified_name=dataset_atlan_qualified_name,
            contract_json=contract_json_str,
        )
        try:
            response = client.asset.save(contract)
            self.logs.info(str(response))
        except AtlanError as e:
            self.logs.error(f"Atlan integration error: {e}")
