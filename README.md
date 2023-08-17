# ocean_protocol_eth_pred

Predict Eth price 

## Install  

### with ocean-lib and data science tools + jupyter into vscode  

conda clean -p
pip cache purge
conda update -n base -c conda-forge conda
conda create --name ocean_tf python=3.10.4
conda activate ocean_tf
conda install -c apple tensorflow-deps==2.9.0
python -m pip install tensorflow-macos==2.9.0
python -m pip install tensorflow-metal==0.5.0


pip3 install matplotlib ccxt eth_account
conda install pandas
conda install scikit-learn

ARCHFLAGS="-arch arm64" pip3 install ocean-lib

pip install ipykernel==6.21.0 --force-reinstall



ETH Prediction Round 3 : 1h timeframe + report:  
  -  03_Data_Sources.ipynb : Data pipeline  
  -  04_Explore.ipynb : Explorartion + Model  
  -  /doc/ETH Prediction Round 3 - jeugregg.pdf : final report  


ETH Prediction Round 4 : 1 hour timeframe:  
  -  05_Explore_april  
  -  06_Model  


ETH Prediction Round 5 : 5 min timeframe:  
  -  07_Data_Sources_05min ( limited to ohlcv data)  
  -  06_Model_05min (Auto-encoder + LSTM)  
  -  Readme 
    - https://github.com/oceanprotocol/predict-eth/blob/main/challenges/main5.md
  -  Results / Prizes
    - 1st place  : https://blog.oceanprotocol.com/here-are-the-winners-of-the-predict-eth-round-5-data-challenge-95f71bcade95

ETH Prediction Round 6 : 5 min timeframe:  
  -  08_Data_Sources_05min (with all data available)  
  -  09_Model_05min (Auto-encoder + LSTM)
    -  Models not optimized (10 epochs max)  
  -  Blog  
    -  https://blog.oceanprotocol.com/predict-eth-round-6-data-challenge-is-live-d305502888f9
  -  Readme  
    -  https://github.com/oceanprotocol/predict-eth/blob/main/challenges/main6.md
  -  Final Transaction  
    -  https://mumbai.polygonscan.com/tx/0x32ddbba3c3f4fc2664570b7f72fce47cbf29f64318a5e445bf8debd917618418
  -  Results / Prizes
    - 2nd place / 15 : https://medium.com/oceanprotocol/here-are-the-winners-of-the-predict-eth-round-6-data-challenge-9b8e8f786170

ETH Prediction Round 7 : 5 min timeframe:  
  -  10_Data_Sources_05min (with all data available)  
  -  11_Model_05min (Auto-encoder + LSTM)
    -  Models with auto-select best encoded features 
  -  Blog  
    -  https://blog.oceanprotocol.com/here-are-the-winners-of-the-predict-eth-round-7-data-challenge-d5ec1c2056e0
  -  Readme  
    -  https://github.com/oceanprotocol/predict-eth/blob/main/challenges/main7.md
  -  Final Transaction  
    -  https://mumbai.polygonscan.com/tx/0xa5c13583cded7e69140ae04e4730837a5e8e97ae4decc7dc9a921e388ca71a39
  -  Results / Prizes
    - 4th place / 80 : https://medium.com/oceanprotocol/predict-eth-round-7-data-challenge-is-live-9be6d7faa4a1

2023/08/02 : ETH Prediction Round weely : 5 min timeframe:
  -  10_Data_Sources_05min (with all data available)  
  -  12_Model_05min (Auto-encoder  2 LSTM layers + LSTM predictor)
  -  Blog  
    -  https://medium.com/oceanprotocol/introducing-challenge-data-farming-378bba28fc97
  -  Readme  
    -  https://github.com/oceanprotocol/predict-eth/blob/main/challenges/challenge-df.md
  -  Final Transaction  
    -  https://mumbai.polygonscan.com/tx/0xc2f8a73272a69e81db02149a21d0ff0899acecbe53077642509cec373175e791

2023/08/09 : round
- 13_Model_05min.ipynb  
  - Test with 6h of lag
  - TRAIN/TEST : 80/20
  - Model without dropout for decoder part of AE

2023/08/16 : round
- 14_Model_05min.ipynb
  - Test with 6h of lag
  - TRAIN/TEST : 80/20
  - remove some feature : sin/cos month
  - normalized by ETH price some economics indices : spx, fvx, dxy because TEST data out of TRAIN range
  - Very slow to train on TRAIN set
  - MSE TEST lower than MSE TRAIN at first