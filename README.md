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
  -  06_Model_05min (model LSTM only for the moment)  


