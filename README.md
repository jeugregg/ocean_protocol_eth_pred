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
