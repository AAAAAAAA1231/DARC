from backend.core.identity import build_project_identity, is_evm_address


def test_chain_contract_id():
    ident = build_project_identity(name="Foo", chain="Ethereum", contract="0x" + "ab" * 20)
    assert ident.project_id.startswith("PROJECT-ETHEREUM-0X")
    assert ident.identity_kind == "chain_contract"
    assert ident.dedup_key.startswith("ethereum:0x")


def test_pre_token_id_stable():
    a = build_project_identity(name="Helium", website="https://x.com", twitter="helium")
    b = build_project_identity(name="Helium", website="https://x.com", twitter="helium")
    c = build_project_identity(name="Helium2", website="https://x.com", twitter="helium")
    assert a.project_id == b.project_id
    assert a.project_id != c.project_id
    assert a.identity_kind == "pre_token"


def test_evm_address():
    assert is_evm_address("0x" + "a" * 40)
    assert not is_evm_address("not-an-address")
