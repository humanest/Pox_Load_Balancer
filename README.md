# Pox_Load_Balancer

How to run the code?
1. modify the topology.in to decide the number of host and client you want to create.
2. create directory /tmp/server_status/ to store the log info.
2. start controller by ```./pox.py log.level --DEBUG Pox_Load_Balancer --policy=2``` and the policy is round robin
3. start mininet topology by ``` sudo python3 mininetTopo.py ```
