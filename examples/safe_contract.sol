// Safe Solidity sample showing checks-effects-interactions and reentrancy guard
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SafeVault {
    mapping(address => uint256) public balances;

    // simple reentrancy guard
    bool private locked;

    modifier noReentrant() {
        require(!locked, "No reentrancy");
        locked = true;
        _;
        locked = false;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external noReentrant {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        // Effects
        balances[msg.sender] -= amount;
        // Interaction after state change
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
    }
}
