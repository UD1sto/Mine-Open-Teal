from typing import Final

from beaker.client import ApplicationClient
from pyteal import *
from beaker import *
from hashlib import sha256

class MineMain(Application):
    owner: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.bytes, default=Global.creator_address()
    )
    evaluator: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.bytes, default=Bytes("")
    )

    auction_end: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0)
    )
    # the states of the supply chain process, the following states are included:

    # 1: Batch is ready to receive stones from miners
    # 2: Batch is full and ready to be transported
    # 3: Batch is in transport 
    # 4: Batch has arrived in the final destonation
    # 5: stone packeting process is finished
    # 6: There is a problem with the process

    state: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(1)
    )
    
    # maximum state that can be reached,
    # it is used in the application for checks
    stateMax: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(6)
    )
    
    # Batch number, the application starts from 1 and increments when an old batch 
    # finished it's process. The applciation does NOT handle batches concurrently 
    batchNo: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(1)
    )

    # The maximum amount of batches, after whitch the contract will stop
    batchNoMax: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(20)
    )

    batchCurrentKg: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0)
    )

    batchMaxKg: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(10)
    )
    
    # The tracking url of the batch
    tracking: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.bytes, default=Bytes("")
    )

    minerStatus: Final[AccountStateValue] = AccountStateValue(
        stack_type=TealType.bytes, descr="the verification status of a miner"
    )

    @create
    def create(self):
        return self.initialize_application_state()

    @opt_in
    def opt_in(self):
        return self.initialize_account_state()

    @external(authorize=Authorize.only(owner))
    def set_evaluator(self, evaluator: abi.Address):
        return Seq(
            self.evaluator.set(evaluator.get()),
        )

    @external
    def minerRequestRole(self):
      return Seq(
        Assert(self.minerStatus.get() != Bytes("Active-Unverified")),
        Assert(self.minerStatus.get() != Bytes("Active-Verified")),
        self.minerStatus.set(Bytes("Active-Unverified"))
      )
    
    @external(authorize=Authorize.only(owner))
    def authorizeMiner(self, miner: abi.Address):

        return Seq(
            [
                # Assert(self.minerStatus[miner.get()].get == Bytes("Active-Unverified")),
                self.minerStatus[miner.get()].set(Bytes("Active-Verified"))
                
            ]
        )

    @external(authorize=Authorize.only(owner))
    def proceedToNext(self):
        return Seq([
            Assert(self.state.get() < Int(5)),
            self.state.set(self.state.get() + Int(1))
        ])


    @external(authorize=Authorize.only(owner))
    def newBatch(self):
        return Seq([
            Assert(self.state.get() == Int(5)),
            self.state.set(Int(1)),
            self.batchNo.set(self.batchNo.get() + Int(1)),
            self.batchCurrentKg.set(Int(0))
        ])

    @external(authorize=Authorize.only(owner))
    def revertOriginalState(self):
        return Seq([
            Assert(self.state.get() < Int(5)),
            self.state.set(self.state.get() + Int(1))
        ])

    @external(authorize=Authorize.only(owner))
    def decrementBatch(self):
        return Seq([
            Assert(self.state.get() != Int(5)),
            self.state.set(Int(1)),
            self.batchNo.set(self.batchNo.get() - Int(1)),
            self.batchCurrentKg.set(Int(0))
        ])

    @external(authorize=Authorize.only(owner))
    def set_tracking(self, url: abi.String):
        return self.tracking.set(url.get())


      # @mint:The miner can mint an ASA that acts as the digital representation of the gemstone they inputed in the system
    # Params:
    #   manager: is set to evaluator temporarily, so that the evaluator could change the metadata of the asset
    #   metadata: The field is set from the miner as part of the self evaluation process
    #   default_frozen: The asset is frozen by default to prevent the miner from transferring the asset to another account

   

    @external
    def inputGem(self, metadata: abi.String):
        return Seq(
            [
            Assert(self.minerStatus.get() == Bytes("Active-Verified")),
            Assert(self.state.get() == Int(1)),
            Assert(self.batchCurrentKg.get() < self.batchMaxKg.get()),
            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetConfig,
                    TxnField.config_asset_name: Bytes("CEJ"),
                    # # TxnField.config_asset_unit_name: Bytes("cej"),
                    TxnField.config_asset_total: Int(1),
                    # TxnField.config_asset_decimals: Int(0),
                    TxnField.config_asset_manager: self.evaluator.get(),
                    # # TxnField.config_asset_clawback: self.owner.get(),
                    # # TxnField.config_asset_reserve: self.address,
                    TxnField.config_asset_metadata_hash: metadata.get(),
                    TxnField.config_asset_default_frozen: Int(1),
                    # TxnField.fee: Int(0),
                }
            )
            
            
        ])

    # passes managerial role for ASA to the owner so that it can unfroze the asset
    # and give the asset a url after is being sold

    @external(authorize=Authorize.only(evaluator))
    def auth_gem(self, aid: abi.Uint64, kgInput: abi.Uint64):
        return Seq(
            [
            Assert(self.state.get() == Int(1)),
            Assert(self.batchCurrentKg.get() + kgInput.get() < self.batchMaxKg.get()),
            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetConfig,
                    TxnField.config_asset: aid.get(),
                    TxnField.config_asset_manager: self.owner.get(),
                }
            ),
            self.batchCurrentKg.set(self.batchCurrentKg.get() + kgInput.get())
            
        ])

        # price is denoted as the ASA's unit name in case that it is decided to make the price constant
        # that will require the contract to hold the CEJ ASA and distribute the balance after the sale

    @external(authorize=Authorize.only(owner))
    def unfreeze_asset(self, asset_id: abi.Uint64, price: abi.String):
        return Seq(
            Assert(self.state.get() == Int(5)),

            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetConfig,
                    TxnField.config_asset: asset_id.get(),
                    TxnField.config_asset_default_frozen: Int(0),
                    TxnField.fee: Int(0),
                    TxnField.config_asset_unit_name: price.get(),
                }
            ),
        )

    @external(authorize=Authorize.only(owner))
    def update_asset_url(self, asset_id: abi.Uint64, url: abi.String):
        return Seq(
            Assert(self.state.get() == Int(5)),
            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetConfig,
                    TxnField.config_asset: asset_id.get(),
                    TxnField.config_asset_url: url.get(),
                    TxnField.fee: Int(0),
                }
            ),
        )

    # self.do_axfer(self.owner, InnerTxn.created_asset_id(), Int(1))

def demo():
    client = sandbox.get_algod_client()

    acct = sandbox.get_accounts().pop()

    print(acct)

    app_client = ApplicationClient(
        client, app=MineMain(), signer=acct.signer)
    
    # Create the application on chain, set the app id for the app client
    app_id, app_addr, txid = app_client.create()

    app_client.fund(1 * consts.algo)

    app_client.opt_in()

    
    app_client.call(MineMain.minerRequestRole)

    # print(initial_stage)

    app_client.call(MineMain.authorizeMiner, miner="OIPXTNJDQI3LUX4MV6ANBHLPTVUXHLUMJ5NOGZNENF2JIK35AWDMUMDX7Q")

    app_client.call(MineMain.set_evaluator, evaluator="OIPXTNJDQI3LUX4MV6ANBHLPTVUXHLUMJ5NOGZNENF2JIK35AWDMUMDX7Q")

    # app_client.call(MineMain.proceedToNext)

    metadata = "test"

    app_client.call(MineMain.inputGem, metadata="0aa1ea9a5a04b78d4581dd6d17742627")

    app_client.call(MineMain.auth_gem, aid=1, kgInput=20)

    app_client.call(MineMain.set_tracking, url="https://test.batchTracking.com")

    app_client.call(MineMain.proceedToNext)

    app_client.call(MineMain.proceedToNext)

    app_client.call(MineMain.proceedToNext)

    app_client.call(MineMain.proceedToNext)

    app_client.call(MineMain.proceedToNext)

    app_client.call(MineMain.unfreeze_asset, asset_id=1, price="10000")

    app_client.call(MineMain.update_asset_url, asset_id=1, url="https://test.cejTracking.com")

    app_client.call(MineMain.newBatch)

    print(
        f"Created App with id: {app_id} and address: {app_addr} in tx: {txid}\n")

    # print(f"result: {result.return_value}")



demo()
