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
