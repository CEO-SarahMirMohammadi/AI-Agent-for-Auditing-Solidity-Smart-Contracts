// Simple example Solidity contract for smoke tests
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Example {
    uint256 public balance;

    // naive deposit
    function deposit() public payable {
        balance += msg.value;
    }

    // unsafe withdraw using call (for demonstration)
    function withdraw(uint256 amount) public {
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
        balance -= amount;
    }
}
