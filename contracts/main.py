from typing import Final

from beaker.client import ApplicationClient
from pyteal import *
from beaker import (
    Application,
    ApplicationStateValue,
    AccountStateValue,
    create,
    opt_in,
    external,
    internal,
    delete,
    bare_external,
    Authorize,
    consts,
    sandbox,
    
)


class MineMain(Application):

    manager: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.bytes, default=Global.creator_address()
    )

    miner: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.bytes, default=Bytes("")
    )

    evaluator: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.bytes, default=Bytes("")
    )

    state: ApplicationStateValue(
        stack_type=TealType.uint64
    )

    stateMax: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(7)
    )

    batchNo: ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(1)
    )

    batchNoMax: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(10)
    )

    batchCurrentKg: ApplicationStateValue(
        stack_type=TealType.uint64
    )

    batchMaxKg: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(1)
    )

    tracking: ApplicationStateValue(
        stack_type=TealType.bytes
    )

    @create
    def initialize_application_state(self, maxKg: abi.Uint64,
                                     eval: abi.Address, min: abi.Address):
        return Seq([
            self.state.set(Int(1)),
            self.batchNo.set(Int(1)),
            self.batchMaxKg.set(maxKg.get()),
            self.evaluator.set(eval.get()),
            self.miner.set(min.get())
        ])

    @opt_in
    def opt_in(self):
        return self.initialize_account_state()

    @external(authorize=Authorize.only(manager))
    def incrementBatch(self):
        return Seq([
            Assert(
                self.state.get() == Int(7)
            ),
            self.state.set(Int(1)),
            self.batchNo.set(self.batchNo.get() + Int(1)),
            self.batchCurrentKg.set(Int(0))
        ])

    @external(authorize=Authorize.only(manager))
    def incrementState(self):
        return Seq([
            Assert(
                self.state.get() < Int(7)
            ),
            self.state.set(self.state.get() + Int(1))
        ])

    @external(authorize=Authorize.only(manager))
    def decrementBatch(self):
        return Seq([
            Assert(
                self.state.get() != Int(7)
            ),
            self.state.set(Int(1)),
            self.batchNo.set(self.batchNo.get() - Int(1)),
            self.batchCurrentKg.set(Int(0))
        ])

    @external(authorize=Authorize.only(manager))
    def set_url(self, url: abi.String):
        return self.url.set(url.get())

    @external(authorize=Authorize.only(miner))
    def inputGem(self, metadata: abi.String):
        return Seq(
            Assert(self.state.get() == Int(1)),
            Assert(self.batchCurrentKg.get() <= self.batchMaxKg.get()),
            self.mint(metadata)
        )

    # @mint:The miner can mint an ASA that acts as the digital representation of the gemstone they inputed in the system
    # Params:
    #   manager: is set to evaluator temporarily, so that the evaluator could change the metadata of the asset
    #   metadata: The field is set from the miner as part of the self evaluation process
    #   default_frozen: The asset is frozen by default to prevent the miner from transferring the asset to another account

    #   Note: the stone never changes the miner's ownership, the client buys it directly from the miner'

    @internal(TealType.uint64)
    def mint(self, metadata: abi.String):
        return Seq(


            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetConfig,
                    TxnField.config_asset_name: Bytes("CEJ"),
                    TxnField.config_asset_unit_name: Bytes("cej"),
                    TxnField.config_asset_total: int(1),
                    TxnField.config_asset_decimals: Int(0),
                    TxnField.config_asset_manager: self.evaluator,
                    TxnField.config_asset_clawback: self.manager,
                    TxnField.config_asset_reserve: self.address,
                    TxnField.config_asset_metadata_hash: metadata,
                    TxnField.config_asset_default_frozen: Int(1),
                    TxnField.fee: Int(0),
                }
            ),
            InnerTxn.created_asset_id(),
        )

    @external(authorize=Authorize.only(evaluator))
    def edit_asset_metadata(self, asset_id: abi.Asset, metadata: abi.String, weight: abi.Uint64):
        return Seq(
            Assert(self.state.get() == Int(1)),
            Assert(self.batchCurrentKg.get() +
                   weight <= self.batchMaxKg.get()),

            self.do_opt_in(asset_id),

            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetConfig,
                    TxnField.config_asset: asset_id,
                    TxnField.config_asset_manager: self.manager,
                    TxnField.config_asset_metadata_hash: metadata,
                    TxnField.fee: Int(0),
                }
            ),

            self.batchCurrentKg.set(self.batchCurrentKg.get() + weight)
        )

    @internal(TealType.none)
    def do_opt_in(self, aid):
        return self.do_axfer(self.address, aid, Int(0))

    @external(authorize=Authorize.only(manager))
    def unfreeze_asset(self, asset_id: abi.Asset, price: abi.String):
        return Seq(
            Assert(self.state.get() == Int(7)),
            self.do_opt_in(asset_id),

            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetConfig,
                    TxnField.config_asset: asset_id,
                    TxnField.config_asset_default_frozen: Int(0),
                    TxnField.fee: Int(0),
                    TxnField.asset_name: price,
                }
            ),
        )

    



    @internal(TealType.none)
    def pay(self, amount: abi.Uint64, asset_id: abi.Asset, priceVer: abi.String):
        return InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: self.miner,
                TxnField.amount: amount,
                TxnField.fee: Int((amount / 1000) * 300),
            }
        )

    @external(authorize=Authorize.only(miner))
    def do_axfer(self, receiver: abi.Address, asset_id: abi.Asset):
        return InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: asset_id,
                TxnField.asset_amount: Int(1),
                TxnField.asset_receiver: receiver,
                TxnField.fee: Int(0),
            }
        )


def demo():
    client = sandbox.get_algod_client()

    acct = sandbox.get_accounts().pop()

    app_client = ApplicationClient(
        client, app=Application(), signer=acct.signer)

    # Create the application on chain, set the app id for the app client
    app_id, app_addr, txid = app_client.create()
    print(
        f"Created App with id: {app_id} and address: {app_addr} in tx: {txid}\n")

    # result = app_client.call(A.hello, name="George")
    # print(f"result: {result.return_value}")


demo()
