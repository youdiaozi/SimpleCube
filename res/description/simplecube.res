CONTAINER simplecube
{
	NAME simplecube;
	INCLUDE Obase;

	GROUP ID_OBJECTPROPERTIES
	{
		// ---------------- OBase.Size+Segments ---------------------------
        GROUP
        {
			// 利用LAYOUTGROUP; 造成OBase.Size+Segments的效果
			LAYOUTGROUP;
            COLUMNS 2;
			
			GROUP
			{
				VECTOR SIMPLECUBE_LEN	{ UNIT METER; MIN 0.0; SCALE_H; CUSTOMGUI SUBDESCRIPTION; }
			}
			GROUP
			{
				COLUMNS 1;
			
				LONG SIMPLECUBE_SUBX { MIN 1; MAX 1000; SCALE_H; }
				LONG SIMPLECUBE_SUBY { MIN 1; MAX 1000; SCALE_H; }
				LONG SIMPLECUBE_SUBZ { MIN 1; MAX 1000; SCALE_H; }
			}
        }
		// ---------------- end OBase.Size+Segments ---------------------------
        
        BOOL SIMPLECUBE_SEP             { }
        BOOL SIMPLECUBE_DOFILLET        { }
        REAL SIMPLECUBE_FRAD            { UNIT METER; MIN 0.0; }
        LONG SIMPLECUBE_SUBF            { MIN 1; MAX 1000; }
	}
	
	// INCLUDE Oprimitiveaxis;
}
